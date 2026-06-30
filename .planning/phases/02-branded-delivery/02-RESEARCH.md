# Phase 2: Branded Delivery - Research

**Researched:** 2026-06-30
**Confidence:** HIGH — all findings verified against live codebase (events extension, giftcards extension, LNBits core) and runtime environment (venv package versions, system fonts)

---

## Executive Summary

Phase 2 layers branded visual delivery on top of the Phase 1 core loop. All required dependencies are already in the LNBits venv (Pillow 12.1.1, pyqrcode, Jinja2 3.1.6) — no new packages needed. The events extension provides direct, copy-ready reference implementations for every technical primitive this phase requires: image compositing (template + QR paste), email delivery (MIMEMultipart + SMTP via global settings), and asset upload (FormData → `POST /api/v1/assets`). The current giftcards extension already has a working `make_qr_png()` and a QR endpoint with `StreamingResponse` — these extend naturally to branded card rendering.

The phase introduces five new technical surfaces: (1) a Pillow-based branded card renderer with user-specified QR/text positions, (2) a magic link email verification flow with a new DB table and 30-min TTL, (3) Jinja2 HTML email templates with two modes (custom text + fancy HTML), (4) an interactive Vue/Quasar card designer with drag-to-place QR + text, and (5) a standalone claim page. The magic link flow is the most novel component — it requires a new `ext_giftcards.magic_links` table, token generation following the Phase 1 `secrets.token_urlsafe()` pattern, TTL-based expiry, and invalidation on card redemption. The card designer is the most frontend-heavy component — it needs client-side drag interaction (pointer events on a canvas/preview), a minimum QR size constraint, and real-time preview rendering without server round-trips.

**Key planning insight:** The phase has a natural internal ordering driven by dependencies: (1) DB migration + models first (everything depends on the schema), (2) card image renderer (needed by email, printable, and preview), (3) card designer UI (depends on render endpoint for final output), (4) magic link flow + claim page (independent of image work but needed for email delivery), (5) email delivery (depends on renderer + magic link), (6) printable PNG download (depends on renderer). The renderer and magic link flow can be built in parallel.

---

## Research Findings

### 1. Branded Card Image Compositing with Pillow

**Question:** How to composite a branded card image (template background + QR at user-specified position + text block at user-specified position with custom font/size/color)?

**Answer:** The events extension at `views_api.py:360-399` provides the exact pattern. The current giftcards `make_qr_png()` at `views_api.py:32-58` generates the QR matrix. The renderer composites three layers: template background → QR code pasted at (x,y) → text block drawn at (x,y) with styled font.

**Verified codebase pattern (events extension, `views_api.py:373-389`):**
```python
# 1. Load template (user-uploaded asset OR bundled fallback)
background_bytes = None
if wave.ticket_image_id:
    asset = await get_public_asset(wave.ticket_image_id)  # from lnbits.core.crud.assets
    if asset:
        background_bytes = asset.data
if background_bytes:
    ticket_image = Image.open(BytesIO(background_bytes)).convert("RGBA")
else:
    default_template = Path(__file__).resolve().parent / "static" / "image" / "ticket.jpg"
    ticket_image = Image.open(default_template).convert("RGBA")

# 2. Paste QR at fixed coords
ticket_image.paste(qr_img, (122, 505))

# 3. Save + return via StreamingResponse
ticket_image.save(output, format="PNG")
output.seek(0)
return StreamingResponse(output, media_type="image/png", headers={...})
```

**Phase 2 extension — text rendering with Pillow (`ImageDraw.text`):**
```python
from PIL import Image, ImageDraw, ImageFont

def _render_card_image_sync(template_bytes, lnurl_url, card_data, design_config):
    template = Image.open(BytesIO(template_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(template)

    # QR at user-specified position
    qr_img = make_qr_png(lnurl_url, size=design_config.qr_size)
    template.paste(qr_img, (design_config.qr_x, design_config.qr_y))

    # Text block at user-specified position with styling
    font = ImageFont.truetype(design_config.font_path, design_config.font_size)
    text_lines = [
        f"{card_data.amount} sats",
        f"For: {card_data.recipient_name}",
        card_data.message,
    ]
    y = design_config.text_y
    for line in text_lines:
        draw.text((design_config.text_x, y), line,
                  fill=design_config.font_color, font=font,
                  anchor=design_config.text_anchor)  # "la"=left-ascender, "ma"=middle-ascender
        y += design_config.font_size + line_spacing

    output = BytesIO()
    template.save(output, format="PNG")
    return output.getvalue()
```

**Critical implementation details:**
- **Must run in `asyncio.to_thread()`** — Pillow is CPU-bound. Pitfall 6 (PITFALLS.md:140-163) and ARCHITECTURE.md Pattern 4 (line 210-238) both mandate this. The events extension QR endpoint runs synchronously because it's a single small QR, but branded card compositing (template open + paste + text draw + save) is heavier. Wrap the entire `_render_card_image_sync` in `asyncio.to_thread()`.
- **QR size minimum:** D-07 mandates a minimum scannable QR size. The existing `make_qr_png()` accepts a `size` param (default 235). For LNURL-withdraw URLs (~80 chars), a QR at 150x150px with error correction level M is reliably scannable at phone-camera distance. Recommend **minimum 150px**, default 200px, user can drag larger. The `make_qr_png()` function already handles resizing via `Image.Resampling.NEAREST`.
- **QR error correction:** pyqrcode defaults to error level 'M' (medium, ~15% recovery). This is sufficient for gift card URLs. Higher levels (Q/H) reduce data capacity but improve scannability when the QR is small or partially obscured. Keep 'M' as default.
- **Text alignment:** Pillow's `ImageDraw.text()` supports `anchor` parameter for alignment: `"la"` (left-ascender), `"ma"` (middle-ascender), `"ra"` (right-ascender). This maps directly to the issuer's text alignment choice (D-08).
- **Font loading:** `ImageFont.truetype(path, size)` loads TTF/OTF fonts. System fonts available at `/usr/share/fonts/truetype/dejavu/` (see §8 below). For bundled fonts, ship TTF files in `static/fonts/` and load via `Path(__file__).resolve().parent / "static" / "fonts" / "DejaVuSans.ttf"`.

**Coordinate model (D-09 — planner's discretion):**
Recommend **normalized fractions** (0.0–1.0) for QR and text positions, stored as JSON fields. This works across all template dimensions (425x650, 1050x600, custom up to 1500x2000) without recalculation. At render time, multiply by actual template dimensions:
```python
qr_x = int(design_config.qr_x_frac * template.width)
qr_y = int(design_config.qr_y_frac * template.height)
```
QR size can also be normalized (fraction of template width) OR stored as absolute pixels with a minimum. Recommend absolute pixels with a minimum of 150, since QR scannability depends on absolute size, not relative.

**Template loading priority:**
1. If `template_asset_id` is set → `get_public_asset(asset_id)` → use `asset.data`
2. If asset not found or no asset_id → fall back to bundled template (portrait or landscape based on `template_name` field)
3. Bundled templates in `static/image/` (D-01: 1 portrait 425x650, 1 landscape 1050x600)

**On-demand rendering (D-28):** No image storage. Render each time via `asyncio.to_thread()`. The render endpoint takes card_id (or token_hash for public), loads the card + design config, composites, returns PNG via `StreamingResponse`. Matches events extension pattern exactly.

---

### 2. Magic Link Email Verification Flow

**Question:** How to implement the magic link flow (generate token, store with TTL, verify, invalidate after redemption)? What DB schema is needed?

**Answer:** The magic link flow is a new component not present in the events extension. It follows the Phase 1 token security pattern (`secrets.token_urlsafe()`, store hash only) but with a TTL and email-scoped lookup.

**Flow (D-11 through D-17):**
```
1. Recipient receives notification email (NO raw_token, NO card image)
   → "You have a gift card waiting from {sender}. Visit /giftcards/claim"

2. Recipient visits /giftcards/claim, enters email
   → POST /giftcards/api/v1/claim {email}
   → Server finds all active cards with recipient_email == email
   → If found: generate magic_link_token (secrets.token_urlsafe(32)),
     store hash + email + expiry (now + 30min) in magic_links table
   → Send magic link email: /giftcards/claim/{magic_link_token}
   → Always return same "check your email" response (D-14: don't reveal if email exists)

3. Recipient clicks magic link → /giftcards/claim/{magic_link_token}
   → GET /giftcards/api/v1/claim/{magic_link_token}
   → Server hashes token, looks up magic_links by hash
   → If valid (not expired, not used): return list of pending cards for that email
   → Frontend shows card list (D-15); recipient picks one
   → Redirect to /giftcards/redeem/{raw_token} for the chosen card

4. After card is redeemed → invalidate magic link (D-16)
   → In mark_redeemed() or a post-redemption hook, delete/invalidate magic_links
     rows associated with that card's email
```

**DB schema — new table `ext_giftcards.magic_links`:**
```sql
CREATE TABLE IF NOT EXISTS giftcards.magic_links (
    id            TEXT PRIMARY KEY,
    token_hash    TEXT NOT NULL UNIQUE,   -- SHA-256 of magic_link_token
    email         TEXT NOT NULL,
    wallet        TEXT NOT NULL,          -- issuer wallet (for scoping/cleanup)
    created_at    TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
    expires_at    TIMESTAMP NOT NULL,     -- created_at + 30 min
    used_at       TIMESTAMP               -- null until consumed
);
CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_email ON {table}(email);
CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_token_hash ON {table}(token_hash);
```

**Token generation (follows Phase 1 D-05 pattern):**
```python
import secrets, hashlib
magic_token = secrets.token_urlsafe(32)
magic_hash = hashlib.sha256(magic_token.encode()).hexdigest()
```
Store only the hash. The raw magic token appears only in the magic link URL sent via email. This matches the security posture of the redemption token (Pitfall 3: never store raw secrets).

**Rate limiting (D-13: max 3 per email per hour):**
Two options:
- **In-memory** (simplest): A dict `{email: [timestamp, ...]}` checked at request time. Lost on restart. Sufficient for MVP.
- **DB-backed**: Query `magic_links` table for `WHERE email = :email AND created_at > :one_hour_ago`, count rows. Survives restarts, works across multiple workers.

Recommend **DB-backed** since the magic_links table already tracks `created_at` and `email`. The rate limit check becomes:
```python
recent = await db.fetchall(
    "SELECT id FROM giftcards.magic_links WHERE email = :email AND created_at > :cutoff",
    {"email": email, "cutoff": one_hour_ago}
)
if len(recent) >= 3:
    raise HTTPException(429, "Too many requests. Please wait and try again.")
```
This is accurate, restart-safe, and requires no new infrastructure.

**Invalidation on redemption (D-16):**
After `mark_redeemed(card_id)`, invalidate magic links for that card's email. Two approaches:
- **Simple:** Delete all magic_links rows for that email (recipient verified, no longer needs magic links).
- **Precise:** Only invalidate if the redeemed card was the last pending one for that email. Overly complex for MVP.

Recommend the simple approach: after redemption, delete `WHERE email = :email`. The recipient can always request a new magic link if they have other pending cards.

**Magic link landing page (D-15 — multiple cards):**
The magic link verification endpoint returns a list of pending cards (id, amount, sender_name, created_at) for the email. The claim.vue page renders this list. When the recipient clicks a card, the frontend needs the `raw_token` to redirect to `/giftcards/redeem/{raw_token}`. **Security consideration:** The magic link verification endpoint should return the `raw_token` for each pending card ONLY after successful magic link verification. This is acceptable because the magic link itself is a verified bearer token (recipient proved email ownership). The raw_token is never sent in the initial email — only revealed after verification.

**Claim page endpoint design:**
- `POST /giftcards/api/v1/claim` — public, no auth. Body: `{email}`. Rate-limited. Always returns `{"message": "If you have pending gift cards, a link has been sent to your email."}` regardless of whether cards exist.
- `GET /giftcards/api/v1/claim/{magic_token}` — public, no auth. Returns list of pending cards with raw_tokens, or 404/410 if token invalid/expired.

---

### 3. Interactive Card Designer (Vue/Quasar)

**Question:** How to build the interactive card designer (drag QR + text on a preview, resize QR with minimum size constraint, client-side preview rendering)?

**Answer:** The card designer is the most frontend-heavy component. LNBits extensions use Vue 3 + Quasar with no build step — `.vue` files are served directly. The designer needs pointer-event-based drag interaction on a preview canvas.

**Approach — native pointer events (no external library):**
The events extension frontend (`events/static/js/index.js`) uses vanilla JS patterns within the Vue component structure. No drag library is bundled. For the card designer, use native HTML5 pointer events on a positioned `<div>` preview:

```vue
<!-- Preview container with template image as background -->
<div class="card-preview" :style="{width: previewWidth + 'px', height: previewHeight + 'px'}">
  <img :src="templateUrl" class="template-bg" />
  
  <!-- Draggable QR code -->
  <div class="draggable-qr"
       :style="{left: qrX + 'px', top: qrY + 'px', width: qrSize + 'px', height: qrSize + 'px'}"
       @pointerdown="startDrag($event, 'qr')"
       @pointermove="onDrag"
       @pointerup="endDrag">
    <img :src="qrPreviewUrl" />
    <!-- Resize handle (bottom-right corner) -->
    <div class="resize-handle" @pointerdown.stop="startResize($event)"></div>
  </div>
  
  <!-- Draggable text block -->
  <div class="draggable-text"
       :style="{left: textX + 'px', top: textY + 'px'}"
       @pointerdown="startDrag($event, 'text')"
       @pointermove="onDrag"
       @pointerup="endDrag">
    <div :style="textStyle">{{ previewText }}</div>
  </div>
</div>
```

**Drag logic (in index.js methods):**
```javascript
startDrag(event, target) {
  this.dragState = {
    target,  // 'qr' or 'text'
    startX: event.clientX,
    startY: event.clientY,
    origX: target === 'qr' ? this.qrX : this.textX,
    origY: target === 'qr' ? this.qrY : this.textY,
  }
  event.target.setPointerCapture(event.pointerId)
},
onDrag(event) {
  if (!this.dragState) return
  const dx = event.clientX - this.dragState.startX
  const dy = event.clientY - this.dragState.startY
  const newX = this.dragState.origX + dx
  const newY = this.dragState.origY + dy
  // Clamp to preview bounds
  if (this.dragState.target === 'qr') {
    this.qrX = Math.max(0, Math.min(newX, this.previewWidth - this.qrSize))
    this.qrY = Math.max(0, Math.min(newY, this.previewHeight - this.qrSize))
  } else {
    this.textX = Math.max(0, Math.min(newX, this.previewWidth))
    this.textY = Math.max(0, Math.min(newY, this.previewHeight))
  }
},
endDrag() { this.dragState = null },

startResize(event) {
  this.resizeState = { startX: event.clientX, origSize: this.qrSize }
  event.target.setPointerCapture(event.pointerId)
},
onResize(event) {
  if (!this.resizeState) return
  const dx = event.clientX - this.resizeState.startX
  const newSize = Math.max(this.minQrSize, this.resizeState.origSize + dx)  // min constraint
  this.qrSize = Math.min(newSize, this.previewWidth - this.qrX)  // don't exceed preview
},
```

**QR minimum size constraint (D-07):**
Set `minQrSize = 150` (pixels on the preview). The resize handler enforces `Math.max(minQrSize, ...)`. The user can make the QR larger but never smaller. Default size = minQrSize.

**Client-side preview (D-06):**
The preview is rendered entirely in the browser — QR image overlaid on template via CSS positioning, text rendered as styled HTML. No server round-trips during drag. The template image is loaded from the asset URL (`/api/v1/assets/{asset_id}/data`) or bundled static path. The QR can be generated client-side for preview (using a JS QR library) OR fetched once from the existing `/giftcards/api/v1/lnurl/{token_hash}/qr` endpoint. Since the card isn't created yet during design, use a placeholder QR (any QR image) for preview positioning — the real QR is generated server-side at render time.

**Coordinate conversion (preview → normalized):**
The preview is scaled to fit the dialog. Store positions as normalized fractions (D-09 recommendation from §1):
```javascript
// On submit, convert preview pixels to fractions
const designConfig = {
  qr_x_frac: this.qrX / this.previewWidth,
  qr_y_frac: this.qrY / this.previewHeight,
  qr_size: this.qrSize,  // absolute pixels (scannability depends on absolute size)
  text_x_frac: this.textX / this.previewWidth,
  text_y_frac: this.textY / this.previewHeight,
  font_family: this.selectedFont,
  font_size: this.fontSize,
  font_color: this.fontColor,
  text_align: this.textAlign,
}
```

**Text styling controls (D-08):**
- Font family: `<q-select>` with bundled font options (DejaVu Sans, DejaVu Serif, + 1-2 more)
- Font size: `<q-input type="number">` or `<q-slider>`
- Font color: `<q-input type="color">` (native color picker) or Quasar color picker
- Text alignment: `<q-btn-toggle>` with left/center/right options

**Template selection:**
- Bundled templates: `<q-select>` or `<q-btn>` group with preview thumbnails (portrait, landscape)
- Custom upload: hidden `<input type="file">` + upload button, matching events extension pattern (`events/static/js/index.vue:972-978`, `index.js:280-323`)

**Integration into existing create dialog:**
The current create dialog (`giftcards/static/js/index.vue:169-302`) has fields for amount, recipient, sender, message, expiry. The card designer extends this dialog with a new section (template selection + drag preview + styling controls) below the existing fields. The `createGiftCard()` method sends the design config along with the existing fields.

---

### 4. Jinja2 HTML Email Templates

**Question:** How to implement Jinja2 HTML email templates in an LNBits extension?

**Answer:** Jinja2 3.1.6 is in the LNBits venv (verified). The events extension uses simple string-based HTML (`services.py:162-173`) rather than Jinja2 templates. Phase 2 uses Jinja2 for richer email templates (D-19).

**Jinja2 rendering pattern:**
```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

_email_templates_dir = Path(__file__).resolve().parent / "static" / "email_templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_email_templates_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)

def render_email_template(template_name: str, **context) -> str:
    template = _jinja_env.get_template(template_name)
    return template.render(**context)
```

**Two email modes (D-18):**
1. **Custom text mode:** Issuer writes subject + body. Minimal HTML wrapper:
   ```python
   html_message = f"<p>{escape(body).replace(chr(10), '<br />')}</p>"
   ```
   This is exactly what the events extension does (`services.py:164`).

2. **Fancy HTML mode:** Jinja2 template with embedded branding:
   ```python
   html_message = render_email_template("fancy.html", 
       sender_name=card.sender_name,
       message=card.message,
       claim_url=claim_url,  # /giftcards/claim (NOT the redemption link)
       amount=card.amount,
   )
   ```

**Email template files (D-19 — 2-3 presets in `static/email_templates/`):**
- `notification.html` — the magic link notification email ("You have a gift card waiting")
- `fancy.html` — branded HTML template for the notification (with embedded styling)
- `custom_text.html` — minimal wrapper for custom text mode

**IMPORTANT — magic link flow changes email content (D-12):**
The initial notification email does NOT contain the branded card image or the redemption link. It contains:
- Sender name
- A link to `/giftcards/claim` (the claim page, NOT the redemption link)
- Optional: the sender's message (as text, not the branded image)

The branded card image and raw_token are only revealed AFTER magic link verification. This means the email attachment (DELV-01: "PNG image attachment") is NOT sent in the initial email. **This is a scope deviation from the requirement as written** — DELV-01 says "email as a PNG image attachment" but D-12 says "initial email does NOT contain the branded PNG." The planner must reconcile this: either (a) the PNG is attached to a SECOND email sent after magic link verification, or (b) the PNG is only viewable on the redemption page (not emailed). The CONTEXT.md decisions (D-11, D-12) take precedence over the requirement text — the magic link flow is a deliberate security improvement. Recommend: the branded PNG is rendered on the redemption page (after magic link verification) and is downloadable from there. The initial email is notification-only.

**Embedded images in HTML email:**
For the fancy HTML mode, images can be embedded via:
1. **CID (Content-ID) attachment** — `MIMEImage` with `Content-ID` header, referenced as `<img src="cid:card-image">`. This is the standard for email-embedded images.
2. **External URL** — `<img src="https://host/giftcards/api/v1/cards/{id}/image">`. Simpler but requires the image endpoint to be publicly accessible and may be blocked by email clients.

The events extension uses external URLs (`services.py:169-173`: `<img src="{ticket_image_url}">`). For Phase 2, since the initial email has no card image (D-12), embedded images are only needed for logos/branding in the fancy template — use CID attachment for any logo image.

**SMTP send (D-22 — reuse global settings):**
Copy the events extension pattern exactly (`services.py:251-291`):
```python
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from lnbits.settings import settings
from lnbits.helpers import is_valid_email_address

async def _send_gift_card_email(to_email, subject, text_body, html_body):
    if not settings.lnbits_email_notifications_enabled:
        raise ValueError("Email notifications are disabled")
    if not is_valid_email_address(settings.lnbits_email_notifications_email):
        raise ValueError(f"Invalid from email: {settings.lnbits_email_notifications_email}")
    if not is_valid_email_address(to_email):
        raise ValueError(f"Invalid email: {to_email}")

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.lnbits_email_notifications_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    username = (settings.lnbits_email_notifications_username
                or settings.lnbits_email_notifications_email)
    with smtplib.SMTP(settings.lnbits_email_notifications_server,
                      settings.lnbits_email_notifications_port) as smtp:
        smtp.starttls()
        smtp.login(username, settings.lnbits_email_notifications_password)
        smtp.sendmail(settings.lnbits_email_notifications_email,
                      [to_email], msg.as_string())
```

**SMTP settings (verified, `settings.py:468-474`):**
- `settings.lnbits_email_notifications_enabled` (bool)
- `settings.lnbits_email_notifications_email` (from address)
- `settings.lnbits_email_notifications_username`
- `settings.lnbits_email_notifications_password`
- `settings.lnbits_email_notifications_server` (default: `smtp.protonmail.ch`)
- `settings.lnbits_email_notifications_port` (default: 587)

**Email send must be offloaded:** SMTP is blocking I/O. Use `asyncio.to_thread()` for the SMTP send, or `create_task()` for fire-and-forget. The events extension uses `create_task(_send_ticket_notification(ticket))` (`services.py:112`). Follow this pattern — trigger email send as a background task, surface errors to the issuer via the delivery status field (D-23, D-26).

**Bounce/failure handling (D-23):**
Wrap SMTP send in try/except, log warning, set `email_status = 'failed'` on the card. Card remains active and redeemable. Issuer can retry. Matches events extension (`services.py:218-220`: `logger.warning(f"Failed to email ticket {ticket.id}: {exc}")`).

---

### 5. Claim Page (`/giftcards/claim`)

**Question:** How to implement the claim page — standalone Vue page, email input, rate limiting, "check your email" response?

**Answer:** The claim page is a new standalone public page, following the same pattern as the existing redeem page (`views.py:16-19`, `routes.json`).

**Route registration:**
1. `views.py` — add public route:
   ```python
   giftcards_generic_router.add_api_route(
       "/claim",
       methods=["GET"],
       endpoint=index_public,  # reuse the same SPA-serving function
   )
   giftcards_generic_router.add_api_route(
       "/claim/{magic_token}",
       methods=["GET"],
       endpoint=index_public,
   )
   ```
2. `routes.json` — add two routes:
   ```json
   {
     "path": "/giftcards/claim",
     "name": "PageGiftCardsClaim",
     "template": "/giftcards/static/js/claim.vue",
     "component": "/giftcards/static/js/claim.js"
   },
   {
     "path": "/giftcards/claim/:magic_token",
     "name": "PageGiftCardsClaimVerify",
     "template": "/giftcards/static/js/claim.vue",
     "component": "/giftcards/static/js/claim.js"
   }
   ```

**Claim page Vue component (`claim.vue` + `claim.js`):**
- **State 1 — Email input:** Simple form with one `<q-input type="email">` and submit button. On submit → `POST /giftcards/api/v1/claim {email}`. Always show "Check your email" confirmation (D-14).
- **State 2 — Magic link verification:** If URL has `:magic_token`, auto-call `GET /giftcards/api/v1/claim/{magic_token}`. If valid, show list of pending cards (D-15). Each card shows amount, sender, created date, and a "Redeem" button → redirect to `/giftcards/redeem/{raw_token}`.
- **State 3 — Invalid/expired link:** Show error message if magic link is invalid or expired.

**API endpoints (in `views_api.py`):**
```python
# Public, no auth — claim request
@giftcards_claim_router.post("/claim")
async def api_claim_cards(data: ClaimRequest) -> dict:
    # Rate limit check (DB-backed, 3/hr per email)
    # Find pending cards for email
    # If found: generate magic link, send email
    # Always return same response
    return {"message": "If you have pending gift cards, a verification link has been sent to your email."}

# Public, no auth — magic link verification
@giftcards_claim_router.get("/claim/{magic_token}")
async def api_verify_claim(magic_token: str) -> dict:
    # Hash token, look up magic_links
    # If valid: return list of pending cards with raw_tokens
    # If invalid/expired: 404 or 410
```

**Rate limiting (D-13 — 3/hr per email):** See §2 above. DB-backed query on `magic_links` table.

**Security considerations:**
- The claim endpoint does NOT reveal whether an email has pending cards (D-14). Same response regardless.
- The magic link token is a bearer token — once verified, it grants access to all pending cards for that email. This is acceptable because the recipient proved email ownership.
- Card ID is never in the claim URL (D-14). Only the magic token.
- The magic link verification response includes `raw_token` for each card — this is the only time raw_token is exposed outside of card creation. It's gated behind email verification.

---

### 6. On-Demand Image Rendering Endpoint

**Question:** How to handle on-demand image rendering (render endpoint that composites template + QR + text, returns PNG via StreamingResponse)?

**Answer:** Extend the existing `lnurl_qr` endpoint pattern (`views_api.py:203-236`). Add a new branded card image endpoint.

**Endpoint design:**
```python
@giftcards_api_router.get("/{card_id}/image")
async def api_card_image(card_id: str, request: Request) -> StreamingResponse:
    """Render branded card image on demand."""
    card = await get_card(card_id)
    if not card:
        raise HTTPException(404, "Gift card not found")
    
    # Build LNURL URL for QR
    lnurl_url = f"{str(request.base_url).rstrip('/')}/giftcards/api/v1/lnurl/{card.token_hash}"
    
    # Render in thread (CPU-bound Pillow)
    png_bytes = await asyncio.to_thread(
        _render_card_image_sync, card, lnurl_url
    )
    
    output = BytesIO(png_bytes)
    return StreamingResponse(
        output,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
```

**Public vs. authenticated access:**
The card image contains the QR (which encodes the LNURL URL with token_hash). The token_hash is NOT the raw_token — it's the SHA-256 hash, which is already in the public LNURL endpoint URL. So the card image endpoint can be public (no auth) if it uses token_hash in the QR. However, the card image also shows the sats amount and message — this is already shown on the public redemption page. **Recommend: public access by card_id** (for embedding in emails/claim page) OR by token_hash (consistent with existing public endpoints). Use token_hash for consistency with the existing `/giftcards/api/v1/lnurl/{token_hash}/qr` endpoint.

**Printable PNG (D-27 — higher resolution):**
Same render function, larger output. Add a `?print=1` query param or a separate endpoint:
```python
@giftcards_api_router.get("/{card_id}/print")
async def api_card_print(card_id: str, request: Request) -> StreamingResponse:
    # Same as image but with scale=2 or scale=3 for print resolution
    png_bytes = await asyncio.to_thread(_render_card_image_sync, card, lnurl_url, scale=3)
    ...
```
The render function multiplies template dimensions and all positions by the scale factor. At scale=3, a 425x650 template becomes 1275x1950 — suitable for printing.

**Download trigger (issuer UI):**
The printable download is triggered from the card list (D-24 — deliver later from card list). A download button opens `/giftcards/api/v1/cards/{card_id}/print` in a new tab with `Content-Disposition: attachment; filename="giftcard.png"` header (add to the StreamingResponse headers for the print endpoint).

---

### 7. Migration Schema for Phase 2 Fields

**Question:** What migration schema is needed for Phase 2 fields?

**Answer:** Add migration `m003_branded_delivery` following the existing pattern (`migrations.py:38-45`). Two parts: (1) new columns on `giftcards.cards`, (2) new `magic_links` table.

**Migration `m003`:**
```python
async def m003_branded_delivery(db):
    # Design config columns on cards table
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN template_asset_id TEXT;")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN template_name TEXT;")  # 'portrait', 'landscape', or custom
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN qr_config TEXT;")      # JSON: {x_frac, y_frac, size}
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN text_config TEXT;")    # JSON: {x_frac, y_frac, font, size, color, align}
    
    # Email delivery columns
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN recipient_email TEXT;")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_status TEXT DEFAULT 'not_sent';")  # not_sent/sent/failed
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_subject TEXT;")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_body TEXT;")
    await db.execute("ALTER TABLE giftcards.cards ADD COLUMN email_template TEXT;")  # 'custom' or 'fancy'
    
    # Magic links table
    await db.execute(f"""
        CREATE TABLE IF NOT EXISTS giftcards.magic_links (
            id            TEXT PRIMARY KEY,
            token_hash    TEXT NOT NULL UNIQUE,
            email         TEXT NOT NULL,
            wallet        TEXT NOT NULL,
            created_at    TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            expires_at    TIMESTAMP NOT NULL,
            used_at       TIMESTAMP
        );
    """)
    table = f"{db.references_schema}magic_links"
    await db.execute(f"CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_email ON {table}(email);")
    await db.execute(f"CREATE INDEX IF NOT EXISTS idx_giftcards_magic_links_token_hash ON {table}(token_hash);")
```

**Design config as JSON columns (qr_config, text_config):**
Using JSON TEXT columns for position/style config is simpler than individual columns and matches how the data is used (loaded as a group, passed to the renderer). Pydantic v1 models can use `Optional[str]` for these and parse with `json.loads()` in the service layer. Alternatively, use nested Pydantic models with `@validator` to serialize/deserialize.

**Model extensions (`models.py`):**
```python
class DesignConfig(BaseModel):
    template_asset_id: Optional[str] = None
    template_name: str = "portrait"  # 'portrait', 'landscape'
    qr_x_frac: float = 0.1
    qr_y_frac: float = 0.7
    qr_size: int = 200  # absolute pixels
    text_x_frac: float = 0.1
    text_y_frac: float = 0.1
    font_family: str = "DejaVuSans"
    font_size: int = 24
    font_color: str = "#000000"
    text_align: str = "left"

class CreateGiftCard(BaseModel):
    # ... existing fields ...
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None  # serialized to qr_config + text_config columns

class GiftCard(BaseModel):
    # ... existing fields ...
    template_asset_id: Optional[str] = None
    template_name: Optional[str] = None
    qr_config: Optional[str] = None      # JSON
    text_config: Optional[str] = None    # JSON
    recipient_email: Optional[str] = None
    email_status: str = "not_sent"
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    email_template: Optional[str] = None
```

**Note on `card_wallet_id`:** STATE.md (line 93) notes that `card_wallet_id` remains in the DB (nullable, always None). Phase 2 code should not rely on it. No migration needed to drop it.

---

### 8. Open-Source Fonts

**Question:** What open-source fonts can be bundled with the extension for text styling?

**Answer:** DejaVu fonts are available on the system at `/usr/share/fonts/truetype/dejavu/` and are the standard open-source font bundled with most Linux distributions. They have a permissive license (BSD-like / public domain for the metrics).

**Available system fonts (verified):**
- `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` — sans-serif regular
- `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` — sans-serif bold
- `/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf` — serif regular
- `/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf` — serif bold
- `/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf` — monospace

**Recommendation — bundle 3 fonts in `static/fonts/`:**
1. `DejaVuSans.ttf` — default sans-serif
2. `DejaVuSerif.ttf` — elegant serif (good for formal gift cards)
3. A third option — either `DejaVuSans-Bold.ttf` (bold sans) or a more decorative font

**Bundling approach:** Copy the TTF files into `giftcards/static/fonts/`. Load via `ImageFont.truetype()`:
```python
from pathlib import Path
_fonts_dir = Path(__file__).resolve().parent / "static" / "fonts"
_font_cache = {}

def get_font(family: str, size: int) -> ImageFont.FreeTypeFont:
    key = (family, size)
    if key not in _font_cache:
        path = _fonts_dir / f"{family}.ttf"
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]
```

**Font licensing:** DejaVu fonts are licensed under the "DejaVu Font License" (a BSD-like free license) — safe to bundle and redistribute. No attribution required in the UI, but include the license file in `static/fonts/LICENSE` for compliance.

**Alternative fonts to consider (if DejaVu isn't desired):**
- Liberation Sans/Serif (metric-compatible with Arial/Times, GPL+exception)
- Noto Sans/Serif (Google, OFL) — available on system at `/usr/share/fonts/truetype/noto/`
- Roboto (Google, OFL) — would need to be downloaded

DejaVu is the safest choice — already on the system, permissive license, good Unicode coverage.

---

### 9. "Show All Pending Cards for Email" Flow

**Question:** How to handle the "show all pending cards for email" flow on the magic link landing page?

**Answer:** After magic link verification (§2, §5), the API returns a list of pending cards. The claim.vue page renders this list.

**CRUD function:**
```python
async def get_pending_cards_by_email(email: str) -> list[dict]:
    """Get all active, non-expired cards for an email (for magic link landing page)."""
    rows = await db.fetchall(
        """SELECT id, amount, sender_name, recipient_name, message, 
                  raw_token, created_at, expires_at
           FROM giftcards.cards 
           WHERE recipient_email = :email 
           AND status = 'active'
           AND (expires_at IS NULL OR expires_at > :now)
           ORDER BY created_at DESC""",
        {"email": email, "now": time.time()},
    )
    return [dict(row) for row in rows]
```

**Important:** This query returns `raw_token` — this is the ONLY endpoint that exposes raw_token outside of card creation. It's gated behind magic link verification (recipient proved email ownership). This is a deliberate security decision per D-11/D-12.

**Claim page list UI (`claim.vue`):**
```vue
<div v-if="pendingCards.length > 0">
  <h5>You have {{ pendingCards.length }} gift card(s) waiting</h5>
  <q-card v-for="card in pendingCards" :key="card.id" class="q-mb-md">
    <q-card-section>
      <div class="text-h6">{{ card.amount }} sats</div>
      <div>From: {{ card.sender_name || 'Anonymous' }}</div>
      <div v-if="card.message">{{ card.message }}</div>
      <div class="text-caption">Received: {{ formatDate(card.created_at) }}</div>
      <q-btn color="primary" label="Redeem" 
             :href="`/giftcards/redeem/${card.raw_token}`" />
    </q-card-section>
  </q-card>
</div>
<div v-else>
  <p>No pending gift cards found for your email.</p>
</div>
```

**Magic link verification endpoint response:**
```python
{
  "cards": [
    {
      "id": "gc_abc123",
      "amount": 50000,
      "sender_name": "Alice",
      "recipient_name": "Bob",
      "message": "Happy birthday!",
      "raw_token": "...",  # for redirect to /giftcards/redeem/{raw_token}
      "created_at": "2026-06-30T...",
      "expires_at": "2026-07-30T..."
    }
  ]
}
```

**Post-redemption invalidation:** When a card is redeemed, the magic link for that email should be invalidated (D-16). Since the magic link grants access to ALL pending cards for an email, and the recipient may have multiple cards, the simplest approach is to invalidate the magic link only when the LAST pending card for that email is redeemed. However, for MVP simplicity, recommend invalidating the magic link immediately on any redemption from that link — the recipient can request a new magic link if they have other pending cards. This is a slight UX inconvenience but simpler and more secure.

---

## Dependency Verification

All required packages verified in the LNBits venv (`/home/exedev/lnbits/.venv`):

| Package | Version | Verified | Purpose |
|---------|---------|----------|---------|
| Pillow | 12.1.1 | `.venv/bin/python -c "import PIL"` | Image compositing, text rendering |
| pyqrcode | (present) | `.venv/bin/python -c "import pyqrcode"` | QR matrix generation |
| Jinja2 | 3.1.6 | `.venv/bin/python -c "import jinja2"` | HTML email templates |
| smtplib | stdlib | — | SMTP email send |
| email.mime | stdlib | — | MIMEMultipart, MIMEText, MIMEImage |
| secrets | stdlib | — | Magic link token generation |
| hashlib | stdlib | — | Token hashing |
| asyncio.to_thread | stdlib | — | Offload CPU-bound rendering |

**No new dependencies needed.** This satisfies Pitfall 7 (no new Python dependencies).

---

## Key Codebase References (Verified)

| Reference | Location | What to Copy |
|-----------|----------|--------------|
| Image compositing (template + QR paste) | `events/views_api.py:360-399` | Template loading (asset vs bundled), paste, StreamingResponse |
| QR generation | `giftcards/views_api.py:32-58` | `make_qr_png()` — reuse directly, extend with size param |
| Email send (MIMEMultipart + SMTP) | `events/services.py:251-291` | SMTP settings, MIMEMultipart construction, sendmail |
| Email notification orchestration | `events/services.py:187-240` | try/except per channel, status flag update, background task |
| Asset upload (frontend) | `events/static/js/index.js:280-323` | `uploadAssetFile()`, `triggerTicketImageUpload()`, `handleTicketImageSelected()` |
| Asset upload (hidden input) | `events/static/js/index.vue:972-978` | `<input type="file" style="display:none" @change>` pattern |
| Asset retrieval (backend) | `lnbits/core/crud/assets.py:47-55` | `get_public_asset(asset_id)` → `Asset` with `.data` bytes |
| Asset upload (backend) | `lnbits/core/services/assets.py:14-51` | `create_user_asset()` — MIME validation, size limit, thumbnail |
| Asset API endpoint | `lnbits/core/views/asset_api.py:141-157` | `POST /api/v1/assets?public_asset=true` → `AssetInfo` with `.id` |
| Migration pattern (add column) | `giftcards/migrations.py:38-45` | `ALTER TABLE ... ADD COLUMN` |
| Migration pattern (new table) | `giftcards/migrations.py:1-35` | `CREATE TABLE IF NOT EXISTS` + index |
| Public page route | `giftcards/views.py:16-19` | `add_api_route` with `index_public` |
| Frontend route | `giftcards/static/routes.json` | path → template + component mapping |
| Email validation | `lnbits/helpers.py:156-158` | `is_valid_email_address(email)` |
| SMTP settings | `lnbits/settings.py:468-474` | `settings.lnbits_email_notifications_*` |
| Asset MIME types | `lnbits/settings.py:312-332` | `image/png`, `image/jpeg` allowed |
| Asset size limit | `lnbits/settings.py:311` | 2.5MB default (`lnbits_max_asset_size_mb`) |
| Background task | `events/services.py:111-112` | `create_task()` for fire-and-forget email |

---

## Risks and Pitfalls (Phase 2 Specific)

1. **Synchronous Pillow rendering blocking event loop (Pitfall 6):** All image rendering MUST use `asyncio.to_thread()`. The events extension QR endpoint runs synchronously (small QR, acceptable), but branded card compositing (template open + paste + text draw + save) is heavier. Do NOT call Pillow directly in an `async def` endpoint.

2. **Synchronous SMTP blocking event loop (Pitfall 6):** SMTP send MUST be offloaded. Use `asyncio.to_thread()` for the SMTP call or `create_task()` for fire-and-forget. The events extension uses `create_task()` (`services.py:112`).

3. **Magic link token security:** Follow Phase 1 pattern — `secrets.token_urlsafe(32)`, store SHA-256 hash only, never log the raw token. The magic link is a bearer token that grants access to all pending cards for an email.

4. **Email enumeration (D-14):** The claim endpoint must return the same response regardless of whether the email has pending cards. Do NOT reveal card existence in the response or in timing.

5. **Rate limit bypass:** The 3/hr rate limit must be enforced server-side (DB-backed), not client-side. Check before generating a magic link, not after.

6. **QR scannability (D-07):** The minimum QR size (150px) must be enforced both in the client-side designer (resize handler) AND validated server-side in the render function. A malicious or buggy client could send a smaller size.

7. **Template asset availability:** User-uploaded templates are stored as assets. If an asset is deleted, the render function must fall back to a bundled template (matching events extension pattern at `views_api.py:379-385`).

8. **XSS via sender message in email (PITFALLS.md:259):** Sender-provided text (message, recipient_name) must be HTML-escaped in email templates. Jinja2 autoescape handles this for HTML templates. For custom text mode, use `html.escape()` (as events extension does at `services.py:164`).

9. **Bundled template assets (D-02 — human_action blocker):** The 2 bundled generic templates (portrait 425x650, landscape 1050x600) must be provided by the user. Planner should generate simple Pillow fallbacks if not provided. These are PNG files in `static/image/`.

10. **Asset upload limits:** Default `lnbits_max_assets_per_user = 1` (`settings.py:337`). This may be too low for users uploading multiple custom templates. The planner should note this — either the setting needs to be increased, or template uploads should use a different mechanism. The events extension uses the same asset system for ticket images, so this limit applies there too. Check if the setting is configurable per-environment.

---

## Plan Ordering Recommendation

Based on the dependency analysis, recommend this internal plan ordering:

1. **Migration + Models** (m003, extend GiftCard/CreateGiftCard, new MagicLink model) — everything depends on the schema
2. **Card image renderer** (`services.py::render_card_image()`, render endpoint) — needed by email, printable, and as the server-side counterpart of the designer
3. **Card designer UI** (extend index.vue create dialog with drag preview + styling) — depends on render endpoint for final output
4. **Magic link flow + claim page** (magic_links CRUD, claim endpoints, claim.vue) — independent of image work
5. **Email delivery** (Jinja2 templates, SMTP send, delivery trigger endpoint) — depends on renderer (for the redemption page image) + magic link (for the claim URL in the email)
6. **Printable PNG download** (print endpoint, download button in card list) — depends on renderer

Plans 2 and 4 can be built in parallel. Plans 3 and 5 depend on 2 and 4 respectively. Plan 6 depends on 2.

---

*Phase: 2-Branded Delivery*
*Research completed: 2026-06-30*
