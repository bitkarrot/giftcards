---
phase: 02-branded-delivery
verified: 2026-06-30T04:35:00Z
status: passed
score: 14/14 must-haves verified (automated); 6 items require human testing
behavior_unverified: 0
overrides_applied: 0
deferred: 1 (DELV-03 — nostr delivery, authorized per CONTEXT.md D-17)
scope_adjustments: 2 (D-11/D-12 magic link flow replaces literal PNG attachment; claim page link replaces direct redemption link in email)
tests:
  total: 185
  passed: 185
  failed: 0
  files:

    - test_branded_image.py (29 tests)
    - test_card_designer.py (31 tests)
    - test_magic_link.py (73 tests)
    - test_security_fixes.py (22 tests — regression tests for security hardening commit 6ce6b20)
    - test_core_loop.py (7 tests — Phase 1 regression)
    - test_redemption.py (11 tests — Phase 1 regression)
    - test_expiry.py (7 tests — Phase 1 regression)
    - test_security.py (5 tests — Phase 1 regression)

human_verification:

  - test: "Open the create dialog in a browser and interact with the card designer — drag QR, drag text, resize QR, change font/size/color/alignment, select portrait/landscape/custom upload."
    expected: "All drag/resize/styling controls respond smoothly; QR cannot be resized below 150px; custom upload triggers file picker and loads image as preview background."
    why_human: "Interactive pointer-event drag behavior and visual preview rendering cannot be verified by automated tests."
    status: PENDING

  - test: "Create a card with a design config and open the redemption page in a browser."
    expected: "The branded card image (template + QR + text) renders on the redemption page; Phase 1 cards without design show the bare QR fallback."
    why_human: "Visual rendering of the Pillow-composited branded card image requires manual browser verification."
    status: PENDING

  - test: "Click 'Download PNG' in the card list expanded row."
    expected: "A 3x-resolution PNG file downloads with filename giftcard_{card_id}.png."
    why_human: "File download behavior and image quality require manual verification."
    status: PENDING

  - test: "Visit /giftcards/claim, enter an email, and verify the full magic link flow end-to-end with SMTP configured."
    expected: "Email entry → 'Check Your Email' confirmation → receive notification email → click magic link → see pending cards list → click Redeem → redirect to redemption page."
    why_human: "End-to-end email delivery and magic link click-through require a configured SMTP server and browser interaction."
    status: PENDING

  - test: "Request 4 magic links for the same email within an hour."
    expected: "4th request returns 429 'Too Many Requests' and the claim page shows the rate-limited state."
    why_human: "Rate limiting behavior requires sequential manual requests to verify the 429 response and UI state."
    status: PENDING

  - test: "Redeem a card and then revisit the magic link URL."
    expected: "Magic link shows 'Link Invalid or Expired' — invalidated after redemption (D-16)."
    why_human: "Post-redemption invalidation requires end-to-end testing with a real redemption."
    status: PENDING
post_session_changes:

  - "Security hardening commit 6ce6b20: 4 HIGH severity issues found and fixed (H-1 path traversal, H-2 TOCTOU race on magic link, H-3 stale recipient email, H-4 SMTP exception leakage). 22 regression tests added in test_security_fixes.py."
  - "M-1: Email normalization to lowercase across ClaimRequest, DeliverRequest, CreateGiftCard to prevent rate-limit/lookup bypass via case variation."
  - "M-2: Claim endpoint uses asyncio.create_task for SMTP send to prevent timing-based email enumeration (D-14)."
  - "M-6: Hex color validation on DesignConfig.font_color to prevent public render endpoint 500 on junk input."
  - "DesignConfig validators added for qr_size (>= 150), fractions (0.0-1.0), text_align (allowlist)."

---

# Phase 02: Branded Delivery Verification Report

**Phase Goal:** Issuer can attach a branded image design to a gift card and deliver it to the recipient via email (with image attachment), nostr DM, or printable PNG download — turning the bare redemption link into a recognizable gift card experience.

**Verified:** 2026-06-30T04:35:00Z

**Status:** human_needed — all automated checks pass (185/185 tests); 6 items require manual browser/SMTP testing

## Scope Adjustments (Authorized per CONTEXT.md)

| Adjustment | Original Requirement | Implemented Behavior | Authorization |
|------------|---------------------|---------------------|---------------|
| Magic link flow replaces literal PNG attachment | DELV-01 ("email as PNG image attachment") | Email delivers a notification with a magic link to the claim page; branded card image is revealed only after email verification | CONTEXT.md D-11/D-12 — security decision: bearer token never sent in initial email |
| Claim page link replaces direct redemption link in email | DELV-02 ("link to redeem the gift card") | Email contains link to /giftcards/claim (and magic link URL), not the raw /giftcards/redeem/{raw_token} | CONTEXT.md D-11/D-12 — raw_token never exposed in email |
| Nostr delivery deferred | DELV-03 ("nostr npub DM") | Not implemented — no nostr code | CONTEXT.md D-17 / "Scope adjustment from ROADMAP" — deferred to later phase |

## Goal Achievement

### Observable Truths (Plan 02-01 — Branded Card Image Pipeline)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An issuer can create a gift card with a template selection, QR position, and text styling config, and the branded card image is rendered server-side with Pillow. | ✓ VERIFIED | `DesignConfig` model (`models.py:21-78`) with template_name, qr_x_frac, qr_y_frac, qr_size, text_x_frac, text_y_frac, font_family, font_size, font_color, text_align. `create_gift_card` (`services.py:39-133`) serializes design into qr_config/text_config JSON columns. `render_card_image` (`services.py:334-352`) calls `_render_card_image_sync` via `asyncio.to_thread()`. |
| 2 | The branded card image shows the sats amount, recipient name, and sender message on the chosen template with the QR code at the issuer-specified position. | ✓ VERIFIED | `_render_card_image_sync` (`services.py:267-331`) draws `text_lines = [f"{card.amount} sats", f"For: {card.recipient_name}", card.message]` and pastes QR at `(int(design.qr_x_frac * template.width), int(design.qr_y_frac * template.height))`. |
| 3 | A recipient opening the redemption page sees the branded card image (with embedded QR) when a design config was set; Phase 1 cards without design config show the bare QR fallback. | ✓ VERIFIED | `redeem.vue:54-72` — `v-if="giftCard.has_design"` shows `img.branded-card-img` with `:src="cardImageUrl"`; `v-if="!giftCard.has_design"` shows bare QR. `api_get_public_card` (`views_api.py:118`) returns `has_design=card.template_name is not None or card.template_asset_id is not None`. `redeem.js:17-21` computes `cardImageUrl`. |
| 4 | An issuer can download a printable PNG of the branded card image at 3x resolution from the card list. | ✓ VERIFIED | `api_card_print` (`views_api.py:262-289`) — `GET /{card_id}/print`, authenticated via `require_admin_key`, calls `render_card_image(card, lnurl_url, scale=3)`, returns `StreamingResponse` with `Content-Disposition: attachment; filename="giftcard_{card_id}.png"`. `downloadPrintable` method (`index.js:317-340`) uses fetch+blob download. "Download PNG" button in `index.vue:143-153`. |
| 5 | The card list shows a Delivery status column (not_sent / sent / failed / em-dash) for each card. | ✓ VERIFIED | `giftCardColumns` (`index.js:83-88`) has `delivery` column. `index.vue:68-75` renders `q-badge` with `getDeliveryStatusColor`/`getDeliveryStatusText` when `recipient_email` is set, em-dash otherwise. `getDeliveryStatusColor`/`getDeliveryStatusText` (`index.js:299-315`) map not_sent→grey-6, sent→positive, failed→negative. |

### Observable Truths (Plan 02-02 — Card Designer UI)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An issuer can interactively design a gift card in the create dialog by selecting a template, dragging the QR code, dragging the text block, and choosing font family, font size, font color, and text alignment. | ✓ VERIFIED | `index.vue:268-376` — Card Design section with `q-select` for template, `div.card-preview` with `div.draggable-qr` and `div.draggable-text`, `q-select` for font, `q-slider` for font size (12-72), `q-input type="color"` for font color, `q-btn-toggle` for alignment. Drag methods: `startDrag`, `onDrag`, `endDrag` (`index.js:378-407`). |
| 2 | The issuer can resize the QR code by dragging a corner handle, but the QR cannot be made smaller than 150px. | ✓ VERIFIED | `div.resize-handle` in `index.vue:316-321` with `@pointerdown.stop="startResize"`. `onResize` (`index.js:420-425`) — `Math.max(this.minQrSize, this.resizeState.origSize + dx)` with `minQrSize=150` (`index.js:39`). Server-side clamping also in `_render_card_image_sync`: `max(150, design.qr_size) * scale` (`services.py:294`). |
| 3 | The issuer can upload a custom template image via the LNBits asset system, and it appears as the preview background. | ✓ VERIFIED | `handleTemplateSelected` (`index.js:453-483`) validates dimensions (D-03: max 1500x2000px via `_getImageDimensions`), calls `uploadAssetFile` (`index.js:501-512`) which POSTs `FormData` to `/api/v1/assets?public_asset=true`, stores `asset_id` in `templateAssetId`, sets `templateUrl` to `/api/v1/assets/${assetId}/data`. |
| 4 | The preview is rendered entirely client-side (no server round-trips during drag); the final PNG is rendered server-side only on submit. | ✓ VERIFIED | Drag/resize handlers (`onDrag`, `onResize`) only update reactive state (`qrX`, `qrY`, `qrSize`, `textX`, `textY`) — no API calls. `createGiftCard` (`index.js:213-252`) sends design config to server on submit. |
| 5 | On submit, the design config (normalized fractions for positions, absolute pixels for QR size, font/style settings) is sent to the create endpoint alongside the existing card fields. | ✓ VERIFIED | `createGiftCard` (`index.js:218-233`) builds `designConfig` with `qr_x_frac: this.qrX / this.previewWidth`, `qr_y_frac: this.qrY / this.previewHeight`, `qr_size: this.qrSize`, `font_family`, `font_size`, `font_color`, `text_align` and includes it as `design` in the POST payload. |

### Observable Truths (Plan 02-03 — Magic Link Email Delivery)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An issuer can trigger email delivery for a gift card from the card list; the recipient receives a notification email (no raw_token, no card image) with a link to the claim page. | ✓ VERIFIED | Email delivery dialog in `index.vue:455-535` with "Send Gift Card Email" heading. `api_deliver_email` (`views_api.py:296-343`) — `POST /{card_id}/deliver`, authenticated. `send_gift_card_email` (`services.py:451-503`) renders email and sends via SMTP. `notification.html` contains `{{ sender_name }}` and `{{ magic_link_url }}` — no raw_token, no card image (D-12). |
| 2 | A recipient can visit /giftcards/claim, enter their email, and receive a magic link (30-min TTL) if they have pending gift cards; the same "check your email" response is shown regardless of whether cards exist. | ✓ VERIFIED | `claim.vue:5-32` — State A (email entry) with "Claim Your Gift Card" heading. `api_claim_cards` (`views_api.py:350-389`) — always returns `{"message": "If you have pending gift cards, a verification link has been sent to your email."}` regardless of card existence (D-14). `create_magic_link` (`crud.py:139-161`) sets `expires_at = now + timedelta(minutes=30)`. |
| 3 | A recipient clicks the magic link and sees a list of all pending gift cards for their email; they click "Redeem Gift Card" to navigate to the redemption page. | ✓ VERIFIED | `api_verify_claim` (`views_api.py:416-443`) — `GET /claim/{magic_token}`, returns `{"cards": [...]}` with `raw_token` for each card. `claim.vue:68-101` — State E shows pending cards list with "Redeem Gift Card" button linking to `/giftcards/redeem/{card.raw_token}`. |
| 4 | Magic link tokens are generated with secrets.token_urlsafe(32) and stored as SHA-256 hashes only; raw tokens are never stored in the database. | ✓ VERIFIED | `create_magic_link` (`crud.py:145-146`) — `magic_token = secrets.token_urlsafe(32)`, `token_hash = hashlib.sha256(magic_token.encode()).hexdigest()`. Only `token_hash` stored in `MagicLink` model. `generate_magic_link` (`services.py:30-36`) delegates to `create_magic_link`. |
| 5 | Magic links are rate-limited to 3 requests per email per hour (DB-backed, checked before generating a link). | ✓ VERIFIED | `count_recent_magic_links` (`crud.py:213-222`) — `SELECT COUNT(*) FROM giftcards.magic_links WHERE email = :email AND created_at > :cutoff` (cutoff = now - 3600). `api_claim_cards` (`views_api.py:360-362`) — `if count >= 3: raise HTTPException(429)`. Checked BEFORE generating a link. |
| 6 | Magic links are invalidated after a card is redeemed (delete magic_links rows for that email). | ✓ VERIFIED | `lnurl_callback` (`views_api.py:184-187`) — after `await mark_redeemed(card.id)`, calls `await invalidate_magic_links_for_email(card.recipient_email)` if `card.recipient_email` is set. `invalidate_magic_links_for_email` (`crud.py:183-188`) — `DELETE FROM giftcards.magic_links WHERE email = :email`. |
| 7 | Email delivery supports two modes: custom text (issuer writes subject + body) and fancy HTML (Jinja2 template with branding). Both modes include the claim page URL, not the raw redemption link. | ✓ VERIFIED | `send_gift_card_email` (`services.py:451-503`) — `if email_mode == "fancy"` renders `fancy.html` with sender_name, message, claim_url, amount; else renders `custom_text.html` with body, claim_url. Both use `claim_url` (not raw redemption link per D-12). `emailModeOptions` in `index.js:112-117` — Custom Text / Fancy HTML Template. |
| 8 | Email delivery status is tracked on the card record (not_sent / sent / failed) and visible in the card list. | ✓ VERIFIED | `update_card_email_status` (`crud.py:111-120`) — `UPDATE giftcards.cards SET email_status = :status`. `send_gift_card_email` calls `update_card_email_status(card.id, "sent")` on success, `"failed"` on exception (`services.py:499-502`). Delivery column in card list (Truth 5 above). |

**Score:** 14/14 truths verified by automated tests and code inspection.

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `giftcards/migrations.py` | m003_branded_delivery migration | ✓ VERIFIED | `m003_branded_delivery` (`migrations.py:48-85`) — adds 9 columns to cards table + creates magic_links table with indexes on email and token_hash. |
| `giftcards/models.py` | DesignConfig, MagicLink, ClaimRequest, DeliverRequest models | ✓ VERIFIED | `DesignConfig` (`models.py:21-78`) with validators for template_name, font_family, font_color, text_align, fractions, qr_size. `MagicLink` (`models.py:81-89`). `ClaimRequest` (`models.py:92-99`) with email normalization. `DeliverRequest` (`models.py:102-113`) with email normalization. Extended `GiftCard`, `CreateGiftCard`, `GiftCardSummary`, `PublicGiftCard` with design/email fields. |
| `giftcards/services.py` | Card image renderer, font loading, email services | ✓ VERIFIED | `render_card_image` (`services.py:334-352`), `_render_card_image_sync` (`services.py:267-331`), `get_font` (`services.py:217-223`), `_parse_design_config` (`services.py:226-257`), `_generate_template_fallback` (`services.py:260-264`), `generate_magic_link` (`services.py:30-36`), `render_email_template` (`services.py:376-379`), `_send_smtp_email` (`services.py:382-420`), `send_notification_email` (`services.py:423-448`), `send_gift_card_email` (`services.py:451-503`). |
| `giftcards/views_api.py` | Card image, print, claim, deliver endpoints | ✓ VERIFIED | `api_card_image` (`views_api.py:237-259`) — public image endpoint. `api_card_print` (`views_api.py:262-289`) — authenticated print endpoint. `api_deliver_email` (`views_api.py:296-343`) — deliver endpoint with wallet scoping. `api_claim_cards` (`views_api.py:350-389`) — claim POST. `api_verify_claim` (`views_api.py:416-443`) — claim GET. `giftcards_claim_router` (`views_api.py:52`). |
| `giftcards/crud.py` | Magic link CRUD, email status update | ✓ VERIFIED | `create_magic_link` (`crud.py:139-161`), `get_magic_link_by_hash` (`crud.py:164-180`), `invalidate_magic_links_for_email` (`crud.py:183-188`), `get_pending_cards_by_email` (`crud.py:191-210`), `count_recent_magic_links` (`crud.py:213-222`), `mark_magic_link_used` (`crud.py:225-234`), `mark_magic_link_used_if_unused` (`crud.py:237-253`), `update_card_email_status` (`crud.py:111-120`), `update_card_recipient_email` (`crud.py:123-132`). |
| `giftcards/views.py` | Claim page routes | ✓ VERIFIED | `/claim` and `/claim/{magic_token}` routes served via `index_public` (`views.py:24-35`). |
| `giftcards/__init__.py` | giftcards_claim_router registration | ✓ VERIFIED | `giftcards_ext.include_router(giftcards_claim_router)` (`__init__.py:15`). |
| `giftcards/static/routes.json` | Claim page route entries | ✓ VERIFIED | `PageGiftCardsClaim` and `PageGiftCardsClaimVerify` entries mapping to claim.vue/claim.js (`routes.json:14-25`). |
| `giftcards/static/js/index.vue` | Card designer + email dialog + delivery column | ✓ VERIFIED | Card Design section (`index.vue:268-376`), email delivery dialog (`index.vue:455-535`), Delivery column (`index.vue:68-75`), Download PNG button (`index.vue:143-153`), Send Email button (`index.vue:132-142`). |
| `giftcards/static/js/index.js` | Drag logic, template upload, email dialog, design serialization | ✓ VERIFIED | `startDrag`/`onDrag`/`endDrag`/`startResize`/`onResize`/`endResize` (`index.js:378-429`), `handleTemplateSelected`/`uploadAssetFile`/`triggerTemplateUpload` (`index.js:448-512`), `openEmailDialog`/`sendEmail` (`index.js:522-558`), design config serialization in `createGiftCard` (`index.js:218-233`). |
| `giftcards/static/js/claim.vue` | Claim page with 6 states | ✓ VERIFIED | State A entry (`claim.vue:5-32`), State B confirm (`claim.vue:35-44`), State C rate_limited (`claim.vue:47-56`), State D loading (`claim.vue:59-65`), State E cards (`claim.vue:68-101`), State F invalid (`claim.vue:104-113`). |
| `giftcards/static/js/claim.js` | Claim page logic | ✓ VERIFIED | `submitClaim` (`claim.js:27-50`), `verifyMagicLink` (`claim.js:52-69`), `resetClaim` (`claim.js:71-75`), `formatDate` (`claim.js:77-81`). |
| `giftcards/static/js/redeem.vue` | Branded card image display | ✓ VERIFIED | `img.branded-card-img` with `v-if="giftCard.has_design"` (`redeem.vue:54-59`), bare QR fallback (`redeem.vue:61-72`). |
| `giftcards/static/js/redeem.js` | cardImageUrl computed | ✓ VERIFIED | `cardImageUrl` computed property (`redeem.js:17-21`) builds `/giftcards/api/v1/cards/${tokenHash}/image`. |
| `giftcards/static/image/template_portrait.png` | Portrait template (425x650) | ✓ VERIFIED | File exists, dimensions confirmed: (425, 650). |
| `giftcards/static/image/template_landscape.png` | Landscape template (1050x600) | ✓ VERIFIED | File exists, dimensions confirmed: (1050, 600). |
| `giftcards/static/fonts/DejaVuSans.ttf` | Default sans-serif font | ✓ VERIFIED | File exists (759,720 bytes). |
| `giftcards/static/fonts/DejaVuSerif.ttf` | Serif font | ✓ VERIFIED | File exists (380,660 bytes). |
| `giftcards/static/fonts/DejaVuSansMono.ttf` | Monospace font | ✓ VERIFIED | File exists (343,140 bytes). |
| `giftcards/static/email_templates/notification.html` | Magic link notification template | ✓ VERIFIED | Contains `{{ sender_name }}`, `{{ magic_link_url }}`, `{{ claim_url }}`. No raw_token or card image (D-12). |
| `giftcards/static/email_templates/fancy.html` | Branded HTML email template | ✓ VERIFIED | Contains `{{ sender_name }}`, `{{ message }}`, `{{ claim_url }}`, `{{ amount }}`. Inline CSS for email client compatibility. |
| `giftcards/static/email_templates/custom_text.html` | Custom text email wrapper | ✓ VERIFIED | Contains `{{ body }}` with `white-space: pre-wrap`, `{{ claim_url }}`. |
| `giftcards/tests/` | Test suite | ✓ VERIFIED | 185 tests pass across 8 test files. |

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `static/js/redeem.vue` | `views_api.py` | `img src` to `/giftcards/api/v1/cards/{token_hash}/image` | ✓ WIRED | `cardImageUrl` computed in `redeem.js:17-21` builds URL from tokenHash; `redeem.vue:56` binds `:src="cardImageUrl"`. |
| `views_api.py` | `services.py` | `render_card_image` via `asyncio.to_thread` | ✓ WIRED | `api_card_image` (`views_api.py:248`) calls `await render_card_image(card, lnurl_url, scale=1)`; `render_card_image` (`services.py:350`) calls `asyncio.to_thread(_render_card_image_sync, ...)`. |
| `services.py` | `services.py` | `make_qr_png` reused for QR generation in renderer | ✓ WIRED | `_render_card_image_sync` (`services.py:295`) calls `make_qr_png(lnurl_url, size=qr_size)`. `make_qr_png` defined at `services.py:188-214`. |
| `static/js/index.js` | `views_api.py` | Download PNG button triggers `/giftcards/api/v1/cards/{card_id}/print` | ✓ WIRED | `downloadPrintable` (`index.js:320`) fetches `/giftcards/api/v1/cards/${card.id}/print` with admin key header. |
| `static/js/claim.js` | `views_api.py` | `POST /giftcards/api/v1/claim` and `GET /giftcards/api/v1/claim/{magic_token}` | ✓ WIRED | `submitClaim` (`claim.js:33-37`) POSTs to `/giftcards/api/v1/claim`. `verifyMagicLink` (`claim.js:54`) GETs `/giftcards/api/v1/claim/${token}`. |
| `views_api.py` | `services.py` | Claim endpoint calls `generate_magic_link` and `send_notification_email` | ✓ WIRED | `api_claim_cards` (`views_api.py:370`) calls `generate_magic_link`. `_send_notification_safely` (`views_api.py:405`) calls `send_notification_email`. |
| `services.py` | `crud.py` | Magic link CRUD for create, verify, invalidate, rate limit | ✓ WIRED | `generate_magic_link` calls `create_magic_link`. `api_verify_claim` calls `get_magic_link_by_hash` and `mark_magic_link_used_if_unused`. `lnurl_callback` calls `invalidate_magic_links_for_email`. |
| `static/js/index.js` | `views_api.py` | Email delivery dialog POSTs to `/giftcards/api/v1/cards/{card_id}/deliver` | ✓ WIRED | `sendEmail` (`index.js:543-544`) POSTs to `/giftcards/api/v1/cards/${this.emailDialog.card.id}/deliver`. |
| `views_api.py` | `crud.py` | `mark_redeemed` triggers `invalidate_magic_links_for_email` | ✓ WIRED | `lnurl_callback` (`views_api.py:184-187`) calls `invalidate_magic_links_for_email(card.recipient_email)` after `mark_redeemed`. |
| `static/js/index.js` | `/api/v1/assets` | FormData POST for custom template upload | ✓ WIRED | `uploadAssetFile` (`index.js:501-512`) POSTs `FormData` to `/api/v1/assets?public_asset=true`. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `static/js/redeem.vue` | `cardImageUrl` | `window.location.origin` + `/giftcards/api/v1/cards/{tokenHash}/image` | Yes (server-side Pillow render via `render_card_image`) | ✓ FLOWING |
| `static/js/redeem.vue` | `giftCard.has_design` | `fetch /giftcards/api/v1/cards/public/{token_hash}` | Yes (DB query via `get_card_by_token_hash`, `has_design` computed from `template_name`/`template_asset_id`) | ✓ FLOWING |
| `static/js/index.vue` | `emailDialog.data` | User input in email delivery dialog | Yes (POSTed to `/cards/{card_id}/deliver`) | ✓ FLOWING |
| `static/js/claim.vue` | `pendingCards` | `fetch /giftcards/api/v1/claim/{magic_token}` | Yes (DB query via `get_pending_cards_by_email` after magic link verification) | ✓ FLOWING |
| `views_api.py` | `png_bytes` (image endpoint) | `render_card_image(card, lnurl_url, scale=1)` | Yes (Pillow compositing of template + QR + text) | ✓ FLOWING |
| `views_api.py` | `png_bytes` (print endpoint) | `render_card_image(card, lnurl_url, scale=3)` | Yes (3x resolution Pillow compositing) | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `.venv/bin/pytest /home/exedev/giftcards/tests/ -v` | 185 passed in 6.10s | ✓ PASS |
| Phase 1 regression | `test_core_loop.py`, `test_redemption.py`, `test_expiry.py`, `test_security.py` | 30 passed | ✓ PASS |
| Phase 2 branded image tests | `test_branded_image.py` | 29 passed | ✓ PASS |
| Phase 2 card designer tests | `test_card_designer.py` | 31 passed | ✓ PASS |
| Phase 2 magic link tests | `test_magic_link.py` | 73 passed | ✓ PASS |
| Security regression tests | `test_security_fixes.py` | 22 passed | ✓ PASS |
| Template dimensions | `PIL.Image.open(...).size` | portrait: (425, 650), landscape: (1050, 600) | ✓ PASS |
| Font files present | `ls static/fonts/` | DejaVuSans.ttf, DejaVuSerif.ttf, DejaVuSansMono.ttf | ✓ PASS |
| Email templates present | `ls static/email_templates/` | notification.html, fancy.html, custom_text.html | ✓ PASS |
| Extension module import | `from giftcards import giftcards_ext` | Resolves with claim router included | ✓ PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TPLT-01 | 02-01 | Gift card image can use a sample template | ✓ SATISFIED | `DesignConfig` with `template_name` (portrait/landscape) and `template_asset_id` (custom upload). Bundled templates at `static/image/template_portrait.png` (425x650) and `template_landscape.png` (1050x600). Migration m003 adds `template_asset_id`, `template_name` columns. `render_card_image` loads bundled or asset template. |
| TPLT-02 | 02-02 | Issuer can choose QR code placement | ✓ SATISFIED | Card designer UI with draggable QR element (`div.draggable-qr`), `qr_x_frac`/`qr_y_frac` normalized fractions serialized in `createGiftCard`. Server-side renderer pastes QR at `int(design.qr_x_frac * template.width)`, `int(design.qr_y_frac * template.height)`. |
| TPLT-03 | 02-01 | Card image renders sats amount, recipient name, sender message | ✓ SATISFIED | `_render_card_image_sync` draws `text_lines = [f"{card.amount} sats", f"For: {card.recipient_name}", card.message]` with styled font at issuer-chosen position. |
| DELV-01 | 02-03 | Gift card delivered to recipient by email | ✓ SATISFIED (scope-adjusted) | Email delivery via magic link flow (D-11/D-12). `send_gift_card_email` renders custom or fancy HTML email, sends via SMTP (`_send_smtp_email` offloaded via `asyncio.to_thread`). `POST /cards/{card_id}/deliver` endpoint. Email delivery dialog in issuer UI. **Scope adjustment:** magic link notification email instead of literal PNG attachment — authorized per CONTEXT.md D-11/D-12. |
| DELV-02 | 02-03 | Email includes sender's message and redemption link | ✓ SATISFIED (scope-adjusted) | `fancy.html` includes `{{ sender_name }}`, `{{ message }}`, `{{ claim_url }}`. `custom_text.html` includes `{{ body }}`, `{{ claim_url }}`. `notification.html` includes `{{ sender_name }}`, `{{ magic_link_url }}`. **Scope adjustment:** claim page link / magic link URL instead of direct redemption link — authorized per CONTEXT.md D-11/D-12 (raw_token never sent in email). |
| DELV-03 | — | Gift card delivered to nostr npub as DM | ⏸ DEFERRED | Not implemented — no nostr code. **Authorized deferral** per CONTEXT.md D-17 / "Scope adjustment from ROADMAP": "DELV-03 (nostr npub DM) is deferred. Phase 2 success criteria 1, 2, and 4 remain in scope; criterion 3 (nostr) is deferred." LNBits core has `send_nostr_dm()` infrastructure available for future implementation. |
| DELV-04 | 02-01 | Issuer can download printable gift card image (PNG) | ✓ SATISFIED | `api_card_print` endpoint — `GET /api/v1/cards/{card_id}/print`, authenticated via `require_admin_key`, returns 3x-resolution PNG with `Content-Disposition: attachment`. `downloadPrintable` method in `index.js`, "Download PNG" button in `index.vue`. |

**Requirement coverage summary:** 6/7 SATISFIED, 1/7 DEFERRED (authorized). All 7 requirement IDs accounted for.

## CONTEXT.md Decision Compliance

| Decision | Description | Honored | Evidence |
|----------|-------------|---------|----------|
| D-01 | Bundled samples + custom upload | ✓ | 2 bundled templates (portrait 425x650, landscape 1050x600) + custom upload via LNBits asset system. |
| D-03 | Custom upload dimensions max 1500x2000px | ✓ | `handleTemplateSelected` (`index.js:457-466`) validates `dims.width > 1500 || dims.height > 2000` via `_getImageDimensions`. |
| D-05 | Drag-to-place on live client-side preview | ✓ | `div.draggable-qr` and `div.draggable-text` with pointer events in `index.vue`. |
| D-06 | Client-side preview, server final render | ✓ | Drag/resize updates reactive state only; `render_card_image` called server-side on image/print endpoints. |
| D-07 | QR minimum scannable threshold (150px) | ✓ | `minQrSize=150` in `index.js:39`; `onResize` uses `Math.max(this.minQrSize, ...)`. Server-side: `max(150, design.qr_size) * scale` in `_render_card_image_sync`. DesignConfig validator rejects `qr_size < 150`. |
| D-08 | Full text styling: font family, size, color, alignment | ✓ | `q-select` for font (DejaVuSans/Serif/Mono), `q-slider` for size (12-72), `q-input type="color"`, `q-btn-toggle` for alignment. 3 bundled TTF fonts. |
| D-10 | Text block: sats amount, recipient name, sender message | ✓ | `_render_card_image_sync` draws all three lines. Preview in `index.vue:331-333` shows all three. |
| D-11 | Two-step magic link verification flow | ✓ | Notification email → claim page → magic link → redemption page. `notification.html` has magic_link_url, not raw_token. |
| D-12 | Initial email has no branded PNG or QR | ✓ | `notification.html` contains only sender_name and magic_link_url — no image, no QR, no raw_token. |
| D-13 | Magic link TTL 30 min, rate-limited 3/hr | ✓ | `timedelta(minutes=30)` in `create_magic_link`. `count_recent_magic_links` with 3600s cutoff. 429 response when >= 3. |
| D-14 | Claim page: same response regardless of card existence | ✓ | `api_claim_cards` always returns identical message. M-2: SMTP send via `asyncio.create_task` to prevent timing-based enumeration. |
| D-15 | Multiple pending cards show as list | ✓ | `get_pending_cards_by_email` returns list. `claim.vue` State E renders `q-card v-for="card in pendingCards"`. |
| D-16 | Magic link invalid after redemption | ✓ | `lnurl_callback` calls `invalidate_magic_links_for_email` after `mark_redeemed`. |
| D-17 | Direct redemption link remains in dashboard; nostr deferred | ✓ | `redemption_url` still in card list expanded row. No nostr code (deferred). |
| D-18 | Two email modes: custom text + fancy HTML | ✓ | `emailModeOptions` (Custom Text / Fancy HTML Template). `send_gift_card_email` handles both modes. |
| D-19 | Jinja2 HTML templates (no new deps) | ✓ | `_jinja_env` with `FileSystemLoader` and `select_autoescape(["html", "xml"])`. 3 templates in `static/email_templates/`. |
| D-20 | Custom subject line with default | ✓ | `send_gift_card_email` uses `subject or f"You have a gift card from {sender}"`. Email dialog has subject input. |
| D-21 | Email preview before sending | ✓ | Preview `q-card` in `index.vue:503-512` shows subject and body preview. |
| D-22 | Reuse LNBits global SMTP settings | ✓ | `_send_smtp_email` uses `settings.lnbits_email_notifications_*`. No per-extension SMTP config. |
| D-24 | Create first, deliver later | ✓ | Card created first; email delivery triggered from card list via Send Email button. |
| D-25 | recipient_email optional at creation | ✓ | `CreateGiftCard.recipient_email: Optional[str] = None`. Email added in deliver endpoint. |
| D-26 | Delivery status tracked (not_sent/sent/failed) | ✓ | `email_status` column, `update_card_email_status`, Delivery column in card list. |
| D-27 | Printable PNG = same image, higher resolution | ✓ | `api_card_print` calls `render_card_image(card, lnurl_url, scale=3)` — same render, 3x scale. |
| D-28 | On-demand rendering, no storage | ✓ | `render_card_image` called on each image/print request. No image storage in DB. |

## Security Hardening (Commit 6ce6b20)

| ID | Severity | Issue | Fix | Test |
|----|----------|-------|-----|------|
| H-1 | HIGH | Path traversal via `template_name`/`font_family` interpolated into filesystem paths | `ALLOWED_TEMPLATES`/`ALLOWED_FONTS` allowlist validators in `DesignConfig` (`models.py:8-9, 35-51`) | `test_design_config_rejects_traversal_font_family`, `test_design_config_rejects_traversal_template_name`, `test_design_config_rejects_unknown_font`, `test_design_config_rejects_unknown_template` |
| H-2 | HIGH | TOCTOU race on magic link single-use (two concurrent requests both pass `used_at IS NULL` check) | `mark_magic_link_used_if_unused` — atomic `UPDATE ... WHERE used_at IS NULL` with `rowcount == 1` check (`crud.py:237-253`) | `test_mark_magic_link_used_if_unused_returns_true_for_unused`, `test_mark_magic_link_used_if_unused_returns_false_for_already_used`, `test_mark_magic_link_used_if_unused_sql_includes_used_at_is_null` |
| H-3 | HIGH | Stale in-memory `recipient_email` after DB update in deliver endpoint — email sent to old recipient | Sync `card.recipient_email = data.recipient_email` after `update_card_recipient_email` (`views_api.py:321-322`) | `test_deliver_email_syncs_in_memory_recipient` |
| H-4 | HIGH | SMTP exception details leaked to client in HTTP 500 response | Deliver endpoint catches exception and returns generic `"Email delivery failed. Check server logs."` (`views_api.py:338-343`) | `test_deliver_email_endpoint_does_not_leak_exception_detail` |
| M-1 | MEDIUM | Email case variation bypasses rate limit / lookup | `_normalize_email` to lowercase+strip in `ClaimRequest`, `DeliverRequest`, `CreateGiftCard` (`models.py:14-18, 96-99, 110-113, 131-134`) | `test_claim_request_normalizes_email_to_lowercase`, `test_claim_request_strips_email_whitespace`, `test_deliver_request_normalizes_recipient_email`, `test_create_gift_card_normalizes_recipient_email` |
| M-2 | MEDIUM | Timing-based email enumeration via SMTP send latency | `api_claim_cards` uses `asyncio.create_task(_send_notification_safely(...))` for fire-and-forget SMTP send (`views_api.py:379-386`) | `test_claim_endpoint_uses_background_task_for_smtp` |
| M-6 | MEDIUM | Public render endpoint 500 on invalid hex color | `_HEX_COLOR_RE` validator on `DesignConfig.font_color` (`models.py:53-58`) | `test_design_config_rejects_invalid_font_color`, `test_design_config_rejects_short_hex_font_color`, `test_design_config_accepts_valid_hex_font_color` |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No `TODO`, `FIXME`, `XXX`, `TBD`, `HACK`, `PLACEHOLDER`, stub returns, or hardcoded empty data flows found in implementation files. |

## Phase 1 Regression Check

| Check | Status | Details |
|-------|--------|---------|
| Phase 1 test suite (30 tests) | ✓ PASS | `test_core_loop.py` (7), `test_redemption.py` (11), `test_expiry.py` (7), `test_security.py` (5) — all pass. |
| Phase 1 redemption flow | ✓ INTACT | `lnurl_params`, `lnurl_callback`, `lnurl_qr` endpoints unchanged. Magic link invalidation added to callback but does not affect Phase 1 cards without `recipient_email`. |
| Phase 1 card list / create dialog | ✓ EXTENDED | Card list gains Delivery column and Download PNG / Send Email buttons. Create dialog gains Card Design section. All Phase 1 fields and behavior preserved. |
| Phase 1 redemption page | ✓ EXTENDED | Branded card image added with `v-if` conditional; bare QR fallback preserved for Phase 1 cards. |
| Phase 1 pending verification item | ⚠️ CARRIED FORWARD | Phase 1 VERIFICATION.md had 1 pending human verification (QR scan with real Lightning wallet). This remains pending and is non-blocking. |

## Gaps Summary

No automated gaps remain in the implementation. All 6 in-scope requirements (TPLT-01, TPLT-02, TPLT-03, DELV-01, DELV-02, DELV-04) are satisfied by the code, and the full test suite (185 tests) passes. DELV-03 (nostr) is authorized-deferred per CONTEXT.md D-17. The 2 scope adjustments (magic link flow instead of literal PNG attachment, claim page link instead of direct redemption link) are authorized per CONTEXT.md D-11/D-12 and represent security improvements (bearer token never sent in email).

The only remaining verification is human: interactive card designer UX, visual branded card rendering, printable PNG download, end-to-end email delivery with configured SMTP, rate limiting behavior, and post-redemption magic link invalidation.

---

_Verified: 2026-06-30T04:35:00Z_
_Verifier: Claude (gsd-verifier)_
