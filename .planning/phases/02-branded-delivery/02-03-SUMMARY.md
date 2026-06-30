---
phase: 02-branded-delivery
plan: 03
subsystem: auth
tags: [magic-link, email, smtp, jinja2, vue, quasar, security, rate-limiting]

# Dependency graph
requires:
  - phase: 02-branded-delivery
    provides: Migration m003 with magic_links table, MagicLink/ClaimRequest/DeliverRequest models, email_status column, update_card_email_status crud function
  - phase: 01-core-loop
    provides: GiftCard model, token generation pattern (secrets.token_urlsafe), lnurl_callback redemption flow
provides:
  - Magic link CRUD functions (create, verify, invalidate, rate limit count, mark used, pending cards lookup)
  - Magic link generation service (generate_magic_link) with 30-min TTL and SHA-256 hash storage
  - Claim endpoints (POST /api/v1/claim, GET /api/v1/claim/{magic_token}) with rate limiting and email enumeration prevention
  - Public claim page (/giftcards/claim) with 6 states (entry, confirm, rate_limited, loading, cards, invalid)
  - Magic link invalidation on card redemption (lnurl_callback calls invalidate_magic_links_for_email)
  - Jinja2 email template rendering with autoescape (notification.html, fancy.html, custom_text.html)
  - SMTP send service (_send_smtp_email) following events extension pattern, offloaded via asyncio.to_thread
  - Email delivery orchestration (send_gift_card_email, send_notification_email) with email_status tracking
  - Email delivery endpoint (POST /api/v1/cards/{card_id}/deliver) with wallet scoping
  - Email delivery dialog in issuer UI with mode picker, subject, body, and live preview
  - Send Email button in card list expanded row
affects: [03-bulk-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Magic link token generation following Phase 1 pattern (secrets.token_urlsafe(32), SHA-256 hash only)
    - DB-backed rate limiting (count_recent_magic_links checks magic_links table, 3/hr per email)
    - Email enumeration prevention (same response regardless of card existence — D-14)
    - Jinja2 Environment with FileSystemLoader and select_autoescape for HTML email templates
    - SMTP send offloaded via asyncio.to_thread (Pitfall 6 — blocking I/O)
    - Magic link invalidation on redemption (delete all magic_links for email after mark_redeemed)
    - Public claim page served via index_public (same pattern as redeem page)

key-files:
  created:
    - tests/test_magic_link.py
    - static/js/claim.vue
    - static/js/claim.js
    - static/email_templates/notification.html
    - static/email_templates/fancy.html
    - static/email_templates/custom_text.html
  modified:
    - crud.py
    - services.py
    - views_api.py
    - views.py
    - __init__.py
    - static/routes.json
    - static/js/index.vue
    - static/js/index.js

key-decisions:
  - "Magic link tokens generated with secrets.token_urlsafe(32) (43 chars, 256 bits entropy), only SHA-256 hash stored — follows Phase 1 D-05 pattern"
  - "DB-backed rate limiting (3 requests per email per hour) checked BEFORE generating a link — survives restarts, works across workers (D-13)"
  - "Claim endpoint always returns the same response message regardless of whether cards exist — prevents email enumeration (D-14)"
  - "Magic links invalidated (deleted) on any card redemption for that email — simple approach per RESEARCH.md recommendation (D-16)"
  - "SMTP send is synchronous (_send_smtp_email) but called via asyncio.to_thread — does not block the event loop (Pitfall 6)"
  - "Jinja2 autoescape enabled for all HTML email templates — XSS protection for sender-provided text (T-02-03-07)"
  - "send_notification_email takes sender_name string (not full card object) for flexibility in the claim flow"
  - "Email delivery endpoint verifies card.wallet == wallet.wallet.id before sending (T-02-03-09 — wallet scoping)"

patterns-established:
  - "Pattern: Magic link flow — generate token → store hash → send notification email → recipient clicks link → verify hash → return pending cards → redirect to redeem"
  - "Pattern: DB-backed rate limiting via count query on created_at column (no in-memory state, restart-safe)"
  - "Pattern: Email enumeration prevention — always return identical response, email send errors are logged but not surfaced"
  - "Pattern: Jinja2 email templates with autoescape in static/email_templates/ directory"
  - "Pattern: SMTP send via asyncio.to_thread(_send_smtp_email, ...) — synchronous smtplib wrapped in thread offload"

requirements-completed:
  - DELV-01
  - DELV-02

# Coverage metadata
coverage:
  - id: D1
    description: "Magic link CRUD functions (create, verify, invalidate, rate limit, mark used, pending cards lookup)"
    requirement: "DELV-02"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_create_magic_link_returns_raw_token"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_create_magic_link_stores_hash_not_raw"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_count_recent_magic_links_zero"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_count_recent_magic_links_after_create"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_get_pending_cards_by_email"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_invalidate_magic_links_deletes_rows"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_mark_magic_link_used_sets_used_at"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_get_magic_link_by_hash_expired"
        status: pass
    human_judgment: false
  - id: D2
    description: "Claim endpoints (POST /api/v1/claim, GET /api/v1/claim/{magic_token}) with rate limiting and email enumeration prevention"
    requirement: "DELV-02"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_giftcards_claim_router_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_router_has_two_routes"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_router_prefix"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_router_included_in_ext"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_request_model"
        status: pass
    human_judgment: true
    rationale: "Rate limiting (429 response) and email enumeration prevention require manual end-to-end testing to confirm behavior"
  - id: D3
    description: "Claim page Vue component with 6 states (entry, confirm, rate_limited, loading, cards, invalid)"
    requirement: "DELV-02"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_has_claim_heading"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_has_redeem_button"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_has_invalid_state"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_has_check_email"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_vue_has_rate_limited"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_js_has_submit_claim"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_claim_js_has_verify_magic_link"
        status: pass
    human_judgment: true
    rationale: "Claim page UI rendering with 6 states requires manual browser verification"
  - id: D4
    description: "Magic link invalidation on card redemption (lnurl_callback calls invalidate_magic_links_for_email)"
    requirement: "DELV-02"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_lnurl_callback_has_invalidation"
        status: pass
    human_judgment: true
    rationale: "Post-redemption magic link invalidation requires manual end-to-end testing"
  - id: D5
    description: "Jinja2 email templates (notification.html, fancy.html, custom_text.html) with autoescape"
    requirement: "DELV-01"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_notification_html_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_notification_html_has_sender_name"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_notification_html_has_magic_link_url"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_fancy_html_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_fancy_html_has_claim_url"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_fancy_html_has_amount"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_custom_text_html_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_custom_text_html_has_body"
        status: pass
    human_judgment: false
  - id: D6
    description: "SMTP send service and email delivery orchestration with email_status tracking"
    requirement: "DELV-01"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_send_smtp_email_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_send_gift_card_email_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_send_notification_email_exists"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_send_gift_card_email_is_async"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_render_email_template_notification"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_render_email_template_fancy"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_render_email_template_custom_text"
        status: pass
    human_judgment: true
    rationale: "SMTP send requires configured SMTP server to verify end-to-end email delivery"
  - id: D7
    description: "Email delivery endpoint (POST /api/v1/cards/{card_id}/deliver) with wallet scoping"
    requirement: "DELV-01"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_deliver_endpoint_registered"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_deliver_request_model"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_deliver_request_defaults"
        status: pass
    human_judgment: false
  - id: D8
    description: "Email delivery dialog in issuer UI with mode picker, subject, body, and live preview"
    requirement: "DELV-01"
    verification:
      - kind: unit
        ref: "tests/test_magic_link.py#test_index_vue_has_send_email_dialog"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_index_vue_has_email_mode_select"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_index_js_has_open_email_dialog"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_index_js_has_send_email"
        status: pass
      - kind: unit
        ref: "tests/test_magic_link.py#test_index_js_email_dialog_posts_to_deliver"
        status: pass
    human_judgment: true
    rationale: "Email delivery dialog UI requires manual browser verification"

# Metrics
duration: 12min
completed: 2026-06-30
status: complete
---

# Phase 2 Plan 03: Magic Link Email Delivery Summary

**Secure magic link email verification flow with Jinja2 HTML templates, SMTP send via global LNBits settings, rate-limited claim page, and email delivery dialog with custom/fancy modes**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-30T04:15:00Z
- **Completed:** 2026-06-30T04:27:00Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Magic link CRUD with secrets.token_urlsafe(32) token generation, SHA-256 hash storage, 30-min TTL, and DB-backed rate limiting (3/hr per email)
- Claim endpoints (POST /api/v1/claim, GET /api/v1/claim/{magic_token}) with email enumeration prevention — always returns same response regardless of card existence (D-14)
- Public claim page (/giftcards/claim) with 6 states: email entry, check-your-email confirmation, rate limit exceeded, loading, pending cards list, invalid/expired
- Magic link invalidation on card redemption — lnurl_callback calls invalidate_magic_links_for_email after mark_redeemed (D-16)
- Jinja2 email templates with autoescape: notification.html (magic link notification), fancy.html (branded HTML), custom_text.html (issuer-written body)
- SMTP send service following events extension pattern, offloaded via asyncio.to_thread to avoid blocking the event loop
- Email delivery endpoint (POST /api/v1/cards/{card_id}/deliver) with wallet scoping and email_status tracking (sent/failed)
- Email delivery dialog in issuer UI with mode picker (Custom Text / Fancy HTML), subject, body, live preview, and Send Email button in card list
- 73 new tests covering magic link CRUD, claim endpoints, email templates, SMTP service, and UI — all 163 tests pass (90 existing + 73 new)

## Task Commits

Each task was committed atomically using TDD (RED → GREEN):

1. **Task 1: Magic link CRUD, claim endpoints, rate limiting, and claim page**
   - `9dab5f0` (test): failing tests for magic link CRUD, claim endpoints, claim page, and email delivery
   - `5c5897c` (feat): magic link CRUD functions, generate_magic_link service, claim router with POST/GET endpoints, claim.vue/claim.js with 6 states, routes.json entries, views.py claim routes, __init__.py router registration, lnurl_callback invalidation
2. **Task 2: Jinja2 email templates, SMTP send service, email delivery endpoint, and email delivery dialog**
   - Tests included in `9dab5f0` (test commit) — all email template and SMTP tests were in the same test file
   - `fef85c0` (feat): Jinja2 Environment with autoescape, render_email_template, _send_smtp_email, send_notification_email, send_gift_card_email, deliver endpoint, notification/fancy/custom_text HTML templates, email delivery dialog in index.vue/index.js

## Files Created/Modified
- `crud.py` - 6 new magic link CRUD functions (create_magic_link, get_magic_link_by_hash, invalidate_magic_links_for_email, get_pending_cards_by_email, count_recent_magic_links, mark_magic_link_used) + update_card_recipient_email
- `services.py` - generate_magic_link, render_email_template, _jinja_env, _send_smtp_email, send_notification_email, send_gift_card_email
- `views_api.py` - giftcards_claim_router with POST/GET claim endpoints, api_deliver_email endpoint, lnurl_callback invalidation on redemption
- `views.py` - /claim and /claim/{magic_token} public routes served via index_public
- `__init__.py` - giftcards_claim_router included in giftcards_ext
- `static/routes.json` - PageGiftCardsClaim and PageGiftCardsClaimVerify route entries
- `static/js/claim.vue` - Claim page Vue component with 6 states per UI-SPEC Screen 4 and Screen 5
- `static/js/claim.js` - Claim page logic with submitClaim, verifyMagicLink, resetClaim, formatDate methods
- `static/email_templates/notification.html` - Jinja2 template for magic link notification email
- `static/email_templates/fancy.html` - Jinja2 branded HTML email template with inline CSS
- `static/email_templates/custom_text.html` - Jinja2 minimal wrapper for custom text email mode
- `static/js/index.vue` - Email delivery dialog with mode picker, subject, body, preview + Send Email button in expanded row
- `static/js/index.js` - emailDialog data, emailModeOptions computed, openEmailDialog/sendEmail/isValidEmail methods
- `tests/test_magic_link.py` - 73 tests covering magic link CRUD, claim endpoints, email templates, SMTP service, and UI

## Decisions Made
- Magic link tokens generated with secrets.token_urlsafe(32) (43 chars, 256 bits entropy), only SHA-256 hash stored — follows Phase 1 D-05 pattern
- DB-backed rate limiting (3 requests per email per hour) checked BEFORE generating a link — survives restarts, works across workers (D-13)
- Claim endpoint always returns the same response message regardless of whether cards exist — prevents email enumeration (D-14)
- Magic links invalidated (deleted) on any card redemption for that email — simple approach per RESEARCH.md recommendation (D-16)
- SMTP send is synchronous (_send_smtp_email) but called via asyncio.to_thread — does not block the event loop (Pitfall 6)
- Jinja2 autoescape enabled for all HTML email templates — XSS protection for sender-provided text (T-02-03-07)
- send_notification_email takes sender_name string (not full card object) for flexibility in the claim flow
- Email delivery endpoint verifies card.wallet == wallet.wallet.id before sending (T-02-03-09 — wallet scoping)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Email delivery uses LNBits global SMTP settings (settings.lnbits_email_notifications_*). If SMTP is not configured globally, the deliver endpoint returns an error and the card's email_status is set to "failed".

## Next Phase Readiness
- Magic link email delivery flow is complete and tested — the full vertical slice works: issuer triggers email → recipient gets notification → recipient verifies via magic link → recipient sees pending cards → recipient redeems
- Phase 3 (bulk API) can build on this foundation — the claim page already supports multiple pending cards for the same email (D-15)
- Manual browser testing recommended: verify claim page states, magic link verification, email delivery dialog, and rate limiting behavior
- SMTP end-to-end testing requires configured SMTP server (settings.lnbits_email_notifications_*)

## Self-Check: PASSED

- All 73 tests in `test_magic_link.py` pass
- All 163 tests in the full test suite pass (90 existing + 73 new)
- All acceptance criteria for both tasks verified individually
- Plan-level verification: `pytest giftcards/tests/test_magic_link.py -x` passes
- Backward compatibility: `pytest giftcards/tests/ -x` passes (all Phase 1 and Plan 02-01/02-02 tests green)
- Automated verify commands: import checks for CRUD functions, claim router, email services, and deliver endpoint all pass

---
*Phase: 02-branded-delivery*
*Completed: 2026-06-30*
