# Phase 2: Branded Delivery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 2-Branded Delivery
**Areas discussed:** Template system & sourcing, QR placement model, Nostr delivery mechanism, Email format (magic link flow)

---

## Template System & Sourcing

### How should the template system work?

| Option | Description | Selected |
|--------|-------------|----------|
| Bundled samples + custom upload | 3 static template images + user-uploaded via LNBits asset system. Matches events extension pattern. | ✓ |
| Bundled samples only | Only static templates, no user upload. | |
| Custom upload only | Only user-uploaded, no bundled samples. | |
| Text-rendered only (no background) | QR + text on solid color, no template image. | |

**User's choice:** Bundled samples + custom upload
**Notes:** Matches events extension pattern (default ticket.jpg + uploadable).

### How should we source the 3 bundled sample templates?

| Option | Description | Selected |
|--------|-------------|----------|
| Generate originals with Pillow | Programmatically generated, no licensing risk. | |
| You provide PNG assets | User provides 3 PNG files before Phase 2 execution. | ✓ |
| Generic placeholder now, themed later | Ship 1 placeholder, defer themed templates. | |
| Source public-domain images | Search and download CC0 images. | |

**User's choice:** You provide PNG assets
**Notes:** Human_action blocker — Phase 2 execution waits on user-provided PNGs.

### What dimensions/spec should the template PNGs be?

| Option | Description | Selected |
|--------|-------------|----------|
| Portrait card ~425x650 (events-like) | Match events extension dimensions. | |
| Landscape ~1050x600 | Standard business card ratio. | |
| Planner decides dimensions | Let planner decide based on best practices. | |

**User's choice:** Other — "Portrait (425x650) + Landscape (1050x600) bundled; user upload any dimension up to 1500x2000; drag QR to position"
**Notes:** User wants flexibility — multiple bundled orientations + custom upload with generous size limit + drag-to-place QR.

### Should the 3 bundled templates be themed or orientation variants?

| Option | Description | Selected |
|--------|-------------|----------|
| Christmas + birthday + generic | 3 themed templates, mix of orientations. | |
| 3 themed, orientation your choice | 3 themed, user picks orientation per template. | |
| 2 generic + custom upload for themes | 2 generic (portrait + landscape), themes come from uploads. | ✓ |

**User's choice:** 2 generic + custom upload for themes
**Notes:** Simplifies sourcing — only 2 generic designs needed. Themed designs (Christmas/birthday) come from user uploads.

### How should the issuer position the QR code?

| Option | Description | Selected |
|--------|-------------|----------|
| Drag on preview in create dialog | Issuer drags QR on live preview, position saved as coords. | ✓ |
| Preset positions (dropdown) | Issuer picks from top-left/center/etc. | |
| Auto-positioned (no user choice) | Planner auto-calculates position. | |

**User's choice:** Drag on preview in create dialog

### Should issuer also drag text position?

| Option | Description | Selected |
|--------|-------------|----------|
| Drag QR + drag text block | Full drag control for both QR and text. | ✓ |
| Drag QR, text auto-placed | Only QR is draggable, text is auto-placed. | |
| Text on web page only, not on image | Text not rendered on image at all. | |

**User's choice:** Drag QR + drag text block

### Should issuer control text styling?

| Option | Description | Selected |
|--------|-------------|----------|
| Planner-default font, no user choice | Consistent across all cards. | |
| Preset font styles + color palette | 2-3 preset styles, small palette. | |
| Full text styling controls | Font family, size, color, alignment. | ✓ |

**User's choice:** Full text styling controls

### How should the drag preview work?

| Option | Description | Selected |
|--------|-------------|----------|
| Live server-rendered preview | Server renders on every change (debounced). | |
| Client-side preview, server final render | Browser renders preview, server renders final PNG on submit. | ✓ |
| No preview, submit-then-review | No live preview, submit then review. | |

**User's choice:** Client-side preview, server final render

---

## QR Placement Model

### How should QR position be stored across multiple template dimensions?

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute pixel coords (x,y) | Simple, but different templates need different coords. | |
| Normalized coords (0.0-1.0) | Works across different template sizes. | |
| Planner decides coord model | Let planner decide based on implementation. | ✓ |

**User's choice:** Planner decides coord model

### Should the issuer be able to resize the QR code?

| Option | Description | Selected |
|--------|-------------|----------|
| Drag to resize QR | Full resize control. | |
| Fixed QR size per template | No resize, planner picks default. | |
| Preset sizes (S/M/L) | 3 preset sizes via dropdown. | |

**User's choice:** Other — "the QR code must be above a specific size or else it cannot be scanned. the planner should pick a sensible default and the user can make it larger but not smaller or else the QR code will not work."
**Notes:** Critical constraint — QR has a minimum scannable size. Issuer can make it larger but not smaller.

### Confirm: planner picks minimum scannable QR size, issuer can make larger but not smaller?

| Option | Description | Selected |
|--------|-------------|----------|
| Min size + drag larger only | Default is minimum, drag to enlarge. | ✓ |
| Fixed at minimum scannable size | No resize control at all. | |

**User's choice:** Min size + drag larger only

---

## Nostr Delivery Mechanism

### How should nostr delivery work?

| Option | Description | Selected |
|--------|-------------|----------|
| Raw npub (NIP-04 DM via default relays) | Matches DELV-03, LNBits core has send_nostr_dm. | |
| NIP-05 identifier (events pattern) | Reuses events pattern, but doesn't match "npub" requirement. | |
| Accept both npub and NIP-05 | Most flexible, covers all recipients. | |
| Defer nostr to later phase | Focus Phase 2 on email + printable only. | ✓ |

**User's choice:** Defer nostr to later phase
**Notes:** Reduces Phase 2 scope. DELV-03 deferred. LNBits core infrastructure (send_nostr_dm, validate_pub_key) exists for future implementation.

### Confirm: Phase 2 scope is now branded image + email + printable PNG, with nostr deferred?

| Option | Description | Selected |
|--------|-------------|----------|
| Confirmed: defer nostr, ship email + printable + branded image | Phase 2 success criteria 1, 2, 4 remain; 3 deferred. | ✓ |
| Nostr as optional last wave | Keep nostr but only if time permits. | |

**User's choice:** Confirmed: defer nostr, ship email + printable + branded image

---

## Email Format (Magic Link Flow)

### How should the branded card image appear in the email?

| Option | Description | Selected |
|--------|-------------|----------|
| PNG attachment + text body with link | Matches DELV-01, works offline, ~200-500KB. | |
| Inline hosted image link + text body | Events pattern, lighter email. | |
| Attachment + inline CID reference | Most compatible, largest email. | |

**User's choice:** Other — "what if we sent the email telling the user they have a gift card waiting for them but in order to redeem it they need to visit the site and enter their email address, and then they will be sent a magic link that expires in 30 min. when they click the magic link that will forward the user to the gift card withdrawal link and then they can scan the QR code for the sats."
**Notes:** User proposed a two-step magic link verification flow instead of sending the bearer token directly in email. Significant security improvement — raw_token never sent in initial email.

### The magic link flow is a new capability — how to handle it?

| Option | Description | Selected |
|--------|-------------|----------|
| Include in Phase 2 | Adds magic link system + claim page + email verification. | ✓ |
| Split: Phase 2 simple email, magic link as separate phase | Ship simple email first, magic link later. | |
| Defer all email to separate phase | Phase 2 = printable + branded image only. | |

**User's choice:** Include in Phase 2

### Should the initial email include the branded PNG image?

| Option | Description | Selected |
|--------|-------------|----------|
| Text notification only (no image) | Image revealed only after magic link verification. | |
| PNG attachment + claim notification | QR in initial email, less secure. | |

**User's choice:** Other — "text notification with the option to use an email template with embedded images to make the email look nice and fancy. something easy to customize, also give the user the option to just send a custom text email with a subject"
**Notes:** Initial email supports both custom text (simple) and fancy HTML template (branded with embedded images). The branded gift card PNG (with QR) is NOT in the initial email — revealed only after magic link verification.

### For the fancy HTML email templates: which approach?

| Option | Description | Selected |
|--------|-------------|----------|
| Planner picks open-source template system | Research MJML, Foundation, etc. | |
| Jinja2 HTML templates (no new deps) | 2-3 preset templates, no new dependencies. | ✓ |
| Issuer writes raw HTML | Full control, risk of broken emails. | |

**User's choice:** Jinja2 HTML templates (no new deps)

### After the recipient clicks the magic link, what do they see?

| Option | Description | Selected |
|--------|-------------|----------|
| Magic link → redemption page (with QR) | Shows branded card + QR, recipient scans to redeem. | ✓ |
| Magic link → auto-trigger LNURL redeem | Wallet prompts to redeem automatically. | |
| Magic link → branded card page + QR + button | QR + "Redeem via Lightning" button. | |

**User's choice:** Magic link → redemption page (with QR)

### How does the claim page work?

| Option | Description | Selected |
|--------|-------------|----------|
| Email only (no card ID revealed) | Don't reveal whether email exists. Standard security. | ✓ |
| Email + card ID / claim code | Attacker needs both email and card ID. | |
| Card ID in URL + email verification | Card ID in link from email, recipient verifies email. | |

**User's choice:** Email only (no card ID revealed)

### Should the issuer still be able to see/copy the direct redemption link?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep direct link + add email magic link flow | Both delivery methods coexist. | ✓ |
| Remove direct link, email-only delivery | More secure, less flexible. | |

**User's choice:** Keep direct link + add email magic link flow
**Notes:** Reviewed twice — user confirmed this choice on review.

### How long should the magic link be valid?

| Option | Description | Selected |
|--------|-------------|----------|
| 30 minutes | Tight security window. | ✓ |
| 24 hours | More forgiving. | |
| Tied to card expiration | Most forgiving, least secure. | |
| Issuer chooses TTL per card | Most flexible. | |

**User's choice:** 30 minutes (confirmed on review)

### What happens if the recipient requests multiple magic links?

| Option | Description | Selected |
|--------|-------------|----------|
| Unlimited retries | Simplest, vulnerable to email bombing. | |
| Rate-limited retries (planner picks limit) | Prevents bombing, allows legitimate retries. | ✓ |
| One active link per card | New invalidates old. | |

**User's choice:** Rate-limited retries — 3 per hour per email

### Should recipient_email be required or optional at card creation?

| Option | Description | Selected |
|--------|-------------|----------|
| Optional at creation, added for email delivery | Most flexible. | ✓ |
| Required for email delivery, optional otherwise | UI guides user. | |
| Always required | Forces email for all cards. | |

**User's choice:** Optional at creation, added for email delivery

### How should SMTP be configured?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse LNBits global SMTP settings | Same as events extension. | ✓ |
| Extension-specific SMTP config | Per-extension SMTP. | |
| Global default + per-extension override | Most flexible, most complex. | |

**User's choice:** Reuse LNBits global SMTP settings

### Should the issuer be able to customize the email subject line?

| Option | Description | Selected |
|--------|-------------|----------|
| Custom subject with default fallback | Defaults to "You have a gift card from {sender}". | ✓ |
| Fixed subject line | No customization. | |
| Planner decides | Captured as planner discretion. | |

**User's choice:** Custom subject with default fallback

### Confirm the email body approach: custom text OR fancy HTML template?

| Option | Description | Selected |
|--------|-------------|----------|
| Custom body text with template wrapper | Custom text wrapped in HTML. | |
| Two modes: custom text OR fancy HTML template | Two distinct modes, issuer picks. | ✓ |
| Always preset template, no custom body | No custom body. | |

**User's choice:** Two modes: custom text OR fancy HTML template

### What happens if the email delivery fails?

| Option | Description | Selected |
|--------|-------------|----------|
| Surface error to issuer, manual retry | Card remains active. Matches events pattern. | ✓ |
| Auto-mark failed + notify issuer | More robust, adds bounce detection. | |
| Planner decides bounce handling | Captured as planner discretion. | |

**User's choice:** Surface error to issuer, manual retry

### Should the issuer see an email preview before triggering delivery?

| Option | Description | Selected |
|--------|-------------|----------|
| Preview before send | Reduces mistakes, small frontend cost. | ✓ |
| No preview, send immediately | Simplest, faster. | |

**User's choice:** Preview before send

### When should the branded card image be generated?

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand (render when requested) | No storage, CPU on each request. Matches events. | ✓ |
| Eager at creation (render once, store) | Faster delivery, needs storage. | |
| Planner decides | Captured as planner discretion. | |

**User's choice:** On-demand (render when requested)

### Should the issuer see email delivery status in the card list?

| Option | Description | Selected |
|--------|-------------|----------|
| Track delivery status (not_sent/sent/failed) | Matches events extension flag. | ✓ |
| No persistent status tracking | Simpler data model. | |
| Full delivery history log | Most informative, more DB complexity. | |

**User's choice:** Track delivery status (not_sent/sent/failed)

### What happens to the magic link after the card is redeemed?

| Option | Description | Selected |
|--------|-------------|----------|
| Magic link invalid after redemption | Most secure. | ✓ |
| Magic link shows 'redeemed' status | Consistent with Phase 1 behavior. | |
| Planner decides | Captured as planner discretion. | |

**User's choice:** Magic link invalid after redemption

### Should the claim page be new standalone or extend existing redeem page?

| Option | Description | Selected |
|--------|-------------|----------|
| New /giftcards/claim page | Clean separation of concerns. | ✓ |
| Extend existing redeem page | One page, two modes. | |
| Planner decides page structure | Captured as planner discretion. | |

**User's choice:** New /giftcards/claim page

### Should the printable PNG be the same image or a separate print-optimized version?

| Option | Description | Selected |
|--------|-------------|----------|
| Same image, higher resolution | One render endpoint, just larger. | ✓ |
| Separate print-optimized layout | Cut lines, fold marks, instructions. | |
| Same image, same resolution | No separate print version. | |

**User's choice:** Same image, higher resolution

### When does email delivery happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Choose delivery at creation time | One card, one method upfront. | |
| Create first, deliver later from card list | Matches events pattern (resend). | ✓ |
| Both: at creation + re-deliver later | Most flexible, more complexity. | |

**User's choice:** Create first, deliver later from card list

### What happens if the recipient has multiple pending gift cards for the same email?

| Option | Description | Selected |
|--------|-------------|----------|
| Show all pending cards for that email | Best UX for bulk (Phase 3). | ✓ |
| Send magic links for all cards in one email | Multiple links in one email. | |
| Planner decides (bulk is Phase 3) | Captured as planner discretion. | |

**User's choice:** Show all pending cards for that email

---

## Claude's Discretion

- QR coordinate model (absolute pixels vs normalized fractions) — must work across multiple template dimensions
- Exact minimum scannable QR size — based on QR error correction level and scanning distance
- QR error correction level (L/M/Q/H)
- Magic link storage schema (new table or fields on card record with TTL)
- Magic link token generation method (follow Phase 1 pattern: secrets.token_urlsafe)
- Font files bundled with extension (open-source fonts for text styling)
- Exact rate limit enforcement mechanism (in-memory vs DB-backed)
- HTML email template designs (2-3 preset Jinja2 templates)
- Claim page Vue component structure and styling
- Card designer Vue component (drag interaction library/approach)

## Deferred Ideas

- Nostr delivery (DELV-03) — deferred to a later phase. LNBits core has send_nostr_dm (NIP-04) and validate_pub_key (accepts npub).
- Email bounce detection with automatic notification — Phase 2 surfaces errors manually.
- Per-extension SMTP config — Phase 2 reuses global LNBits SMTP.
- Separate print-optimized layout (cut lines, fold marks) — Phase 2 ships same-image-higher-res.
- MJML or Foundation for Emails for fancier email templates — Phase 2 uses Jinja2 (no new deps).
- Issuer-chosen magic link TTL per card — Phase 2 uses fixed 30-min TTL.
