# Phase 2: Branded Delivery - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers branded visual delivery for gift cards: an interactive card designer (template selection, drag-to-place QR + text, full text styling), a secure email delivery flow with magic link verification, and printable PNG download. The bare redemption link from Phase 1 becomes a recognizable, branded gift card experience.

**In scope:**
- Template system: 2 bundled generic templates (portrait + landscape) + user-uploaded custom templates
- Interactive card designer: drag QR + drag text block on a live client-side preview, full text styling controls
- Email delivery with magic link verification flow (email notification → claim page → magic link → redemption page)
- Printable PNG download (same branded image, higher resolution)
- Delivery status tracking (not_sent / sent / failed)
- New `/giftcards/claim` standalone page for recipient email verification

**Out of scope (deferred):**
- Nostr delivery (DELV-03) — deferred to a later phase
- Bulk CSV creation — Phase 3
- REST API — Phase 3
- Issuer dashboard with filters — Phase 3

**Scope adjustment from ROADMAP:** DELV-03 (nostr npub DM) is deferred. Phase 2 success criteria 1, 2, and 4 remain in scope; criterion 3 (nostr) is deferred. Email delivery model changed from "email contains redemption link directly" (DELV-01/02 as written) to a two-step magic link verification flow (more secure — bearer token never sent in initial email).

</domain>

<decisions>
## Implementation Decisions

### Template System
- **D-01:** Bundled samples + custom upload. Ship 2 generic bundled templates (1 portrait 425x650, 1 landscape 1050x600) in `static/image/`. Custom templates uploaded via the LNBits asset system (`POST /api/v1/assets?public_asset=true` → `asset_id`), matching the events extension pattern (`wave.ticket_image_id`).
- **D-02:** User-provided PNG assets. The 2 bundled generic templates are provided by the user (human_action blocker — Phase 2 execution cannot complete without them). Planner should generate simple Pillow fallbacks if assets aren't provided by execution time, but final assets are user-supplied.
- **D-03:** Custom upload dimensions: any size up to 1500x2000px. Planner validates dimensions on upload and rejects oversized images.
- **D-04:** Themed templates (Christmas, birthday, etc.) come from user uploads, NOT bundled. The 2 bundled templates are generic (no holiday theming). This simplifies sourcing — only 2 generic designs needed.

### Card Designer (QR + Text Placement)
- **D-05:** Drag-to-place on a live client-side preview in the create dialog. Issuer drags both the QR code and a text block on a preview of the template image. Positions are saved on the card record.
- **D-06:** Client-side preview, server final render. The preview is rendered in the browser (QR + text overlaid on template via canvas/CSS) in real-time during drag. The final PNG is rendered server-side with Pillow only on submit/delivery. No server round-trips during drag.
- **D-07:** QR size has a minimum scannable threshold (planner picks the exact minimum, e.g., ~150x150px). Issuer can drag a corner handle to make the QR LARGER but not smaller. Default size is the minimum. This prevents unscannable QR codes.
- **D-08:** Full text styling controls: issuer picks font family, font size, font color, and text alignment for the rendered text block (amount, recipient name, sender message). Planner bundles font options with the extension (e.g., DejaVu Sans, and 2-3 other open-source fonts bundled in `static/fonts/`).
- **D-09:** QR coordinate model (absolute pixels vs normalized fractions) is planner's discretion. Must work across multiple template dimensions (425x650, 1050x600, custom up to 1500x2000).
- **D-10:** Text block contains: sats amount, recipient name, sender message (TPLT-03). All three fields rendered on the image at the issuer-chosen position with issuer-chosen styling.

### Email Delivery — Magic Link Flow
- **D-11:** Two-step verification flow replaces direct link-in-email. The initial email is a notification ("You have a gift card waiting from {sender}"), NOT the redemption link. Recipient visits `/giftcards/claim`, enters their email, receives a magic link (30-min TTL), clicks it → redirected to the redemption page (`/giftcards/redeem/{raw_token}`) which shows the branded card + QR.
- **D-12:** Initial email does NOT contain the branded PNG or QR. The branded card image is only revealed after magic link verification. This is a security decision — the bearer token (raw_token) is never sent in the initial email.
- **D-13:** Magic link TTL: 30 minutes. Rate-limited retries: max 3 magic link requests per email per hour (prevents email bombing while allowing legitimate retries).
- **D-14:** Claim page (`/giftcards/claim`) is a new standalone page. Recipient enters email only (no card ID revealed). If email matches pending cards, magic link is sent. If no match, same "check your email" message is shown (don't reveal whether email exists). Card ID is not in the claim URL.
- **D-15:** If recipient has multiple pending cards for the same email, the magic link reveals a list of all pending gift cards. Recipient picks which one to redeem. (Supports future Phase 3 bulk creation.)
- **D-16:** Magic link becomes invalid immediately after the card is redeemed. Recipient cannot re-access the card page via magic link post-redemption.
- **D-17:** Direct redemption link (`/giftcards/redeem/{raw_token}`) remains visible in the issuer dashboard for copy/paste (Phase 1 feature preserved). Printable PNG still contains the QR. Both delivery methods coexist — issuer chooses per card.

### Email Format
- **D-18:** Two email modes: (a) custom text email — issuer writes their own subject + body text, minimal HTML wrapper; (b) fancy HTML template — preset Jinja2 HTML template with embedded images for branding. Issuer picks the mode when triggering delivery.
- **D-19:** Jinja2 HTML templates (no new dependencies). 2-3 preset HTML email templates bundled in `static/email_templates/`. Jinja2 is already in the LNBits stack via FastAPI/Starlette.
- **D-20:** Custom subject line: issuer can set a custom email subject when triggering delivery. Defaults to "You have a gift card from {sender_name}" if not set.
- **D-21:** Email preview: issuer sees a preview of the email (subject + body) before sending, in the delivery dialog. Can edit subject/body, then send.
- **D-22:** SMTP config: reuse LNBits global SMTP settings (`settings.lnbits_email_notifications_*`), same as events extension. No per-extension SMTP config. If SMTP isn't configured globally, email delivery is disabled with a clear error.
- **D-23:** Bounce/failure handling: if email send fails (SMTP error, bounce, invalid address), surface the error to the issuer in the dashboard. Card remains active and redeemable. Issuer can retry delivery manually. No automatic bounce detection (matches events extension pattern — logs warning, returns error result).

### Delivery Flow
- **D-24:** Create first, deliver later. Card is created first (with template/QR/text config), then issuer picks delivery method from the card list (email / download PNG / copy direct link). Card can be delivered multiple ways. Matches events extension pattern (resend email from list).
- **D-25:** `recipient_email` is optional at card creation. Issuer can create a card without email (for direct link / printable delivery). Email is added when triggering email delivery from the card list.
- **D-26:** Delivery status tracked on card record: `not_sent` / `sent` / `failed`. Issuer sees this in the card list. Can re-trigger delivery. Matches events extension (`email_notification_sent` flag).

### Printable PNG
- **D-27:** Printable PNG is the same branded card image (template + QR + text) at a higher resolution suitable for printing. One render endpoint, just larger output. No separate print-optimized layout (no cut lines, fold marks, or instructions).

### Image Generation
- **D-28:** On-demand rendering. Card image is generated when requested (email send, printable download, image endpoint), not stored at creation time. Re-rendered each time with Pillow + `asyncio.to_thread()`. Matches events extension pattern (QR endpoint renders on-the-fly). No image storage needed.

### Claude's Discretion
- QR coordinate model (absolute pixels vs normalized fractions) — must work across multiple template dimensions
- Exact minimum scannable QR size (e.g., 150x150px) — based on QR error correction level and scanning distance
- QR error correction level (L/M/Q/H) — balance between scannability and data capacity
- Magic link storage schema (new table or fields on card record with TTL)
- Magic link token generation method (follow Phase 1 pattern: `secrets.token_urlsafe`)
- Font files bundled with extension (open-source fonts for text styling)
- Exact rate limit enforcement mechanism (in-memory vs DB-backed)
- HTML email template designs (2-3 preset Jinja2 templates)
- Claim page Vue component structure and styling
- Card designer Vue component (drag interaction library/approach — native HTML5 drag, pointer events, or a Vue draggable library if already available in the LNbits frontend stack)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project requirements and research
- `.planning/PROJECT.md` — Project scope, core value, constraints, and key decisions.
- `.planning/REQUIREMENTS.md` — v1 requirements; Phase 2 covers TPLT-01, TPLT-02, TPLT-03, DELV-01, DELV-02, DELV-04. DELV-03 (nostr) deferred.
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria, and dependencies.
- `.planning/research/SUMMARY.md` — Research conclusions: stack (Pillow, pyqrcode, smtplib), architecture, pitfalls, phase ordering rationale. Lines 47-56 cover delivery features. Line 195 flags template image licensing.
- `.planning/research/ARCHITECTURE.md` — LNBits extension anatomy and component boundaries.
- `.planning/research/PITFALLS.md` — Critical security and operational pitfalls (especially Pitfall 6: synchronous image/email blocking event loop).

### Prior phase context
- `.planning/phases/01-core-loop/01-CONTEXT.md` — Phase 1 decisions (D-01 through D-15), especially D-01/D-02 (LNURL-withdraw redemption), D-05 (token security), D-08 (atomic redemption guard). Phase 2 layers on top of these.

### Reference codebase (events extension — primary pattern source)
- `/home/exedev/events/views_api.py` §360-400 — Image compositing pattern: template + QR paste at fixed coords, `get_public_asset()` for user-uploaded backgrounds, fallback to `static/image/ticket.jpg`, `StreamingResponse` with PNG output.
- `/home/exedev/events/services.py` §120-290 — Email delivery pattern: `MIMEMultipart`, `MIMEText`, SMTP via `settings.lnbits_email_notifications_*`, `_send_ticket_email_notification()`, nostr delivery via `send_user_notification` (NIP-05 only — NOT used in Phase 2 since nostr is deferred).
- `/home/exedev/events/static/js/index.js` §275-320 — Frontend asset upload pattern: `uploadAssetFile()` → `POST /api/v1/assets?public_asset=true` → `asset_id`, `triggerTicketImageUpload()`, `handleTicketImageSelected()`.
- `/home/exedev/events/static/js/index.vue` — Template upload UI, `ticket_image_id` display, download template link.
- `/home/exedev/events/migrations.py` §158 — `m005_add_image_banner` migration pattern for adding image columns.

### LNBits core (asset system + nostr)
- `/home/exedev/lnbits/lnbits/core/services/assets.py` — `create_user_asset()`: validates MIME type, size limits, creates thumbnail, stores asset. Reuse for custom template uploads.
- `/home/exedev/lnbits/lnbits/core/views/asset_api.py` — Asset API endpoints: `GET /{asset_id}/data` (public asset data), `GET /{asset_id}/thumbnail`.
- `/home/exedev/lnbits/lnbits/core/services/nostr.py` — `send_nostr_dm()` and `fetch_nip5_details()`. NOT used in Phase 2 (nostr deferred) but referenced for future Phase 3+ nostr implementation.
- `/home/exedev/lnbits/lnbits/utils/nostr.py` — `validate_pub_key()` (accepts npub), `hex_to_npub()`. For future nostr work.

### Current giftcards extension (Phase 1 code to extend)
- `giftcards/views_api.py` §32-56 — `make_qr_png()`: existing QR generation with pyqrcode + PIL. Reuse/extend for branded card rendering.
- `giftcards/views_api.py` §203-230 — `lnurl_qr` endpoint: existing QR PNG endpoint pattern with `StreamingResponse`.
- `giftcards/models.py` — Current models: `GiftCard`, `CreateGiftCard`, `GiftCardSummary`, `PublicGiftCard`, `CreateGiftCardResponse`. Extend with template/QR/text/email fields.
- `giftcards/migrations.py` — Current migrations: `m001_initial`, `m002_add_raw_token`. Add `m003` for Phase 2 fields.
- `giftcards/static/js/index.vue` — Current issuer UI: create dialog, card list with expand. Extend with card designer + delivery actions.
- `giftcards/static/js/redeem.vue` — Current redemption page. Magic link redirects here after verification.
- `giftcards/static/routes.json` — Frontend route definitions. Add `/giftcards/claim` route.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `make_qr_png()` in `giftcards/views_api.py` — QR generation with pyqrcode + PIL. Extend for branded card compositing (paste QR onto template at user-specified coords).
- `get_public_asset()` from `lnbits.core.crud.assets` — Retrieve user-uploaded template images by asset_id. Events extension uses this for `wave.ticket_image_id`.
- `create_user_asset()` from `lnbits.core.services.assets` — Upload custom templates. Validates MIME type, size, creates thumbnail. Events frontend calls `POST /api/v1/assets?public_asset=true`.
- `MIMEMultipart` + `MIMEText` + `smtplib` — Email delivery primitives. Events extension's `_send_ticket_email_notification()` is a direct reference for the SMTP send logic.
- `settings.lnbits_email_notifications_*` — Global SMTP config (server, port, username, password, from email). Reuse for gift card email delivery.
- `settings.is_nostr_notifications_configured()` — Nostr notification check (NOT used in Phase 2, but available for future).
- Jinja2 (via FastAPI/Starlette) — HTML email template rendering. No new dependency needed.
- `asyncio.to_thread()` — Offload CPU-bound Pillow rendering (research locked, Pitfall 6).

### Established Patterns
- Image compositing: `Image.open(template).convert("RGBA")` → `paste(qr_img, (x, y))` → `save(output, format="PNG")` → `StreamingResponse(output, media_type="image/png")`. Events extension does exactly this at `views_api.py:382`.
- Asset upload: frontend `FormData` → `POST /api/v1/assets?public_asset=true` → store `asset_id` on record. Events extension does this at `index.js:280`.
- Email send: `MIMEMultipart("alternative")` → attach text + HTML → `smtplib.SMTP` + `starttls()` + `login()` + `sendmail()`. Events extension at `services.py:251`.
- Migrations: async `mNNN_name(db)` functions calling `db.execute()`. Sequential, idempotent.
- Frontend routes: `static/routes.json` defines path → template mapping. Add new route for claim page.
- Pydantic v1 models with `@validator` for input validation.

### Integration Points
- `giftcards_static_files` in `__init__.py` — Add `static/email_templates/` and `static/fonts/` directories for bundled assets.
- `static/routes.json` — Add `/giftcards/claim` route → `static/js/claim.vue`.
- `views.py` — Add claim page route (public, no auth, like redeem page).
- `views_api.py` — Add: card image render endpoint, email delivery trigger endpoint, claim/magic link endpoints, printable download endpoint.
- `models.py` — Extend `GiftCard` and `CreateGiftCard` with: `template_asset_id`, `qr_position`, `qr_size`, `text_position`, `text_style` (font/size/color/alignment), `recipient_email`, `email_status`, `email_subject`, `email_body`, `email_template`.
- `migrations.py` — Add `m003` for new fields + magic link table.
- `services.py` — Add: `render_card_image()`, `send_gift_card_email()`, `generate_magic_link()`, `verify_magic_link()`.
- `crud.py` — Add: magic link CRUD, card update with template/design fields, email status update.

</code_context>

<specifics>
## Specific Ideas

- Card designer should feel like a mini design tool — drag QR and text on a live preview, with styling controls. Client-side preview for responsiveness, server render for the final PNG.
- The magic link flow is inspired by secure gift card platforms — the recipient gets a notification, verifies their email, then sees the card. The raw_token is never exposed in the initial email.
- Email should support both a quick "custom text" mode (issuer types a personal message) and a "fancy HTML template" mode (branded, embedded images, looks professional). Two distinct modes, issuer picks.
- Claim page should be simple and trustworthy — just an email field, clean design, "check your email" confirmation. No card ID or sensitive info in the URL.
- Multiple cards for the same email should show as a list after magic link verification — recipient picks which to redeem. This sets up Phase 3 bulk creation.
- QR minimum size is a hard constraint — the planner must ensure the QR is always scannable. User can make it bigger but never smaller than the minimum.
- Printable PNG is just a high-res version of the same image — no separate print layout. Keep it simple.

</specifics>

<deferred>
## Deferred Ideas

- **Nostr delivery (DELV-03)** — Deferred to a later phase. LNBits core has `send_nostr_dm()` (NIP-04) and `validate_pub_key()` (accepts npub), so the infrastructure exists. Future implementation should accept raw npub + default relays, or NIP-05 identifiers. Phase 2 focuses on email + printable.
- **Email bounce detection with automatic notification** — Phase 2 surfaces errors to the issuer manually. Automatic bounce detection (via return-path or webhook) could be added later.
- **Per-extension SMTP config** — Phase 2 reuses global LNBits SMTP. Per-extension SMTP override could be added if needed.
- **Separate print-optimized layout (cut lines, fold marks)** — Phase 2 ships same-image-higher-res. A dedicated print layout could be a future enhancement.
- **MJML or Foundation for Emails for fancier email templates** — Phase 2 uses Jinja2 HTML templates (no new deps). If richer email templates are needed, MJML could be adopted in a future phase.
- **Issuer-chosen magic link TTL per card** — Phase 2 uses fixed 30-min TTL. Per-card TTL could be added later.

</deferred>

---

*Phase: 2-Branded Delivery*
*Context gathered: 2026-06-29*
