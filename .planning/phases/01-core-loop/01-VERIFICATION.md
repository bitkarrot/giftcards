---
phase: 01-core-loop
verified: 2026-06-29T20:00:00Z
reverified: 2026-06-29T22:20:00Z
status: human_needed (2 of 3 manual checks completed post-session)
score: 7/8 must-haves verified
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "Recipient can redeem the card by scanning the QR code with any Lightning wallet; the payout completes successfully."
    test: "Scan the LNURL QR code with a real Lightning wallet and complete the withdrawal."
    expected: "Wallet receives the sats, the card status changes to redeemed, and the public page shows the redeemed state."
    why_human: "The LNURL callback logic is tested in isolation, but the full chain from QR generation → wallet scan → callback → payout is not exercised by automated tests."
human_verification:
  - test: "Create a gift card through the issuer UI or via POST /giftcards/api/v1/cards and verify the issuer wallet balance decreases by the card amount."
    expected: "Card is created with the provided fields and the issuer wallet balance is reduced by the card amount."
    why_human: "No automated test exercises the create endpoint or wallet debit behavior end-to-end."
    status: "DONE (2026-06-29 post-session) — Verified via API call + DB inspection. Card created, issuer wallet debited, no card wallet created."
  - test: "Open the redemption URL in a browser/incognito window."
    expected: "The page renders the amount, sender name, personal message, and a scannable QR code."
    why_human: "Visual rendering and user-facing layout require manual review."
    status: "DONE (2026-06-29 post-session) — Verified via browser. Redemption page renders correctly with card details and QR code."
  - test: "Scan the LNURL QR code with a real Lightning wallet and complete the withdrawal."
    expected: "Wallet receives the sats, the card status changes to redeemed, and the public page shows the redeemed state."
    why_human: "The full QR → wallet scan → LNURL callback → payout chain requires a real wallet and camera."
    status: "PENDING — Non-blocking, can be done during Phase 2."
post_session_changes:
  - "Architecture refactor: removed per-card wallet creation. Sats stay in issuer wallet, paid directly at redemption (withdraw extension pattern)."
  - "Migration m002: added raw_token and redemption_url columns."
  - "LNURL fixes: route name for url_for, CallbackUrl scheme kwarg, timezone-aware datetime comparison."
  - "Frontend fixes: Quasar :model-value binding, dialog formatting, redemption URL display."
  - "Proxy headers: uvicorn --proxy-headers --forwarded-allow-ips '*' for correct external URLs."
  - "Extension icon: 128x128 PNG added to config.json and installed_extensions table."
  - "DB cleanup: 10 card wallets deleted, sats reclaimed, 20 bad apipayments rows removed."
  - "Tests: all 30 tests updated and passing with new architecture."
---

# Phase 01: Core Loop Verification Report

**Phase Goal:** Anyone can create a sats-denominated gift card with a unique secure redemption link and a recipient can redeem it via Lightning — the full end-to-end loop — before any other feature is built.

**Verified:** 2026-06-29T20:00:00Z

**Status:** human_needed

**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Issuer can create a gift card specifying amount, expiration, recipient/sender names, and message; the issuer wallet is debited at creation time. | ✓ VERIFIED (post-session) | `CreateGiftCard` model has all fields; `api_create_card` is wired to `create_gift_card`, which calls `update_wallet_balance` to debit the issuer wallet; `index.vue` form submits to the endpoint. **Post-session:** Manually verified via API call + DB inspection — card created, issuer wallet debited, no card wallet created. |
| 2 | Each created card has a unique, unguessable redemption link; opening the link shows the card value and sender message. | ✓ VERIFIED (post-session) | `generate_token` uses `secrets.token_urlsafe(32)` + SHA-256; `CreateGiftCardResponse` returns `raw_token`, `redemption_url`, and `lnurl_url`. `api_get_public_card` returns safe public fields; `redeem.vue` renders them. **Post-session:** Manually verified via browser — redemption page renders correctly. |
| 3 | Recipient can redeem the card by scanning the QR code with any Lightning wallet; the payout completes successfully. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `lnurl_params` returns `LnurlWithdrawResponse`; `lnurl_callback` atomically claims the card, pays the invoice, and marks it redeemed. `test_redemption.py` covers the callback in isolation, but the full QR → wallet scan chain is not exercised. |
| 4 | A card already redeemed cannot be redeemed again; concurrent redemption attempts do not result in double-spend. | ✓ VERIFIED | `mark_redeeming` uses `UPDATE ... WHERE token_hash = :hash AND status = 'active'` and returns `None` if `rowcount == 0`; `test_concurrent_redemption_no_double_spend` proves exactly one success and one error. |
| 5 | An expired card displays an expired status and cannot be redeemed; locked sats are automatically returned to the issuer wallet. | ✓ VERIFIED | `get_expired_active_cards` + `mark_card_expired` + `reclaim_card_sats` form the expiry sweep; `test_expiry.py` proves expired cards are marked, callbacks reject them, and sats move back to the issuer wallet (or are credited directly in the D-04 fallback). |
| 6 | Raw token is not exposed in public/list API responses; token hashes are not exposed in list/public responses. | ✓ VERIFIED | **Post-session change:** `raw_token` IS now stored in DB (migration m002, user decision) to enable `redemption_url` reconstruction. However, `raw_token` and `token_hash` are still NOT exposed in public/list API responses. `test_token_hash_not_in_list_response` and `test_public_endpoint_safe_fields` confirm sensitive fields are omitted. |
| 7 | The LNURL callback validates the `k1` token and `pr` invoice before attempting payment. | ✓ VERIFIED | `lnurl_callback` rejects missing/empty `pr` and `k1` before locking; `test_mismatched_k1_returns_error_and_leaves_card_active` and `test_missing_pr_returns_error_and_leaves_card_active` pass. |
| 8 | If the Lightning payment fails or is pending, the card returns to the active state so the recipient can retry. | ✓ VERIFIED | `pay_and_complete` raises on `PaymentError` or non-success `Payment` status; `lnurl_callback` catches exceptions, calls `reset_card_to_active`, and returns a generic `LnurlErrorResponse`. `test_payment_error_resets_card_to_active` and `test_pending_payment_resets_card_to_active` pass. |

**Score:** 7/8 truths verified (1 present, behavior-unverified) — updated 2026-06-29 post-session

### Deferred Items

No deferred items identified in this phase. All Phase 1 requirements are addressed; Phase 2/3 features are intentionally absent.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `giftcards/__init__.py` | Extension bootstrap, router assembly, start/stop lifecycle | ✓ VERIFIED | Registers routers, static files, and `create_permanent_unique_task("ext_giftcards", wait_for_expiry)`. |
| `giftcards/models.py` | Pydantic v1 models | ✓ VERIFIED | `CreateGiftCard`, `GiftCard`, `GiftCardSummary`, `PublicGiftCard`, `CreateGiftCardResponse` present; `raw_token` appears only in response model. |
| `giftcards/migrations.py` | Initial schema | ✓ VERIFIED | `m001_initial` creates `giftcards.cards` with `token_hash` unique and indexes on `wallet` and `(status, expires_at)`. |
| `giftcards/crud.py` | DB I/O + atomic guards | ✓ VERIFIED | `create_card`, `get_card_by_token_hash`, `get_cards_by_wallet`, `mark_redeeming`, `mark_redeemed`, `reset_card_to_active`, `mark_card_expired`, `get_expired_active_cards` all present. |
| `giftcards/services.py` | Business logic | ✓ VERIFIED | `generate_token`, `create_gift_card`, `pay_and_complete`, `reclaim_card_sats` present. **Post-session refactor:** `create_card_wallet` removed; sats stay in issuer wallet, paid directly at redemption (withdraw extension pattern). |
| `giftcards/views_api.py` | REST + LNURL endpoints | ✓ VERIFIED | `api_create_card`, `api_get_cards`, `api_get_public_card`, `lnurl_params`, `lnurl_callback`, `lnurl_qr` present and wired. |
| `giftcards/views.py` | SPA routes | ✓ VERIFIED | `giftcards_generic_router` exposes `/` and `/redeem/{raw_token}`. |
| `giftcards/static/js/index.vue` | Issuer UI | ✓ VERIFIED | Create dialog, card list table, copy/export actions present. |
| `giftcards/static/js/index.js` | Issuer page logic | ✓ VERIFIED | Loads cards, creates cards via `LNbits.api.request`, handles result and copy. |
| `giftcards/static/js/redeem.vue` | Public redemption UI | ✓ VERIFIED | Active, redeemed, expired, not-found, and callback-error state cards present. |
| `giftcards/static/js/redeem.js` | Public page logic | ✓ VERIFIED | Computes SHA-256 in browser, fetches public card, detects `?error=1`, renders QR. |
| `giftcards/tasks.py` | Background expiry sweep | ✓ VERIFIED | `_expire_gift_cards` + `wait_for_expiry` with `run_interval(60, ...)` present. |
| `giftcards/tests/*.py` | Test suites | ✓ VERIFIED | 30 tests pass: `test_core_loop.py` (7), `test_redemption.py` (11), `test_expiry.py` (7), `test_security.py` (5). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `static/js/index.vue` | `views_api.py` | `LNbits.api.request` to `POST /giftcards/api/v1/cards` and `GET /giftcards/api/v1/cards` | ✓ WIRED | `createGiftCard` and `loadGiftCards` call the endpoints. |
| `static/js/redeem.vue` | `views_api.py` | `fetch` to `/giftcards/api/v1/cards/public/{token_hash}` and `img src` to `/giftcards/api/v1/lnurl/{token_hash}/qr` | ✓ WIRED | `loadGiftCard` and `qrCodeUrl` use the public endpoints. |
| `views_api.py` | `services.py` | `create_gift_card` and `pay_and_complete` | ✓ WIRED | `api_create_card` calls `create_gift_card`; `lnurl_callback` calls `pay_and_complete`. |
| `services.py` | `lnbits.core.services.payments` | `update_wallet_balance` and `pay_invoice` | ✓ WIRED | Imported and called in `create_gift_card` and `pay_and_complete`. |
| `views_api.py` | `crud.py` | `mark_redeeming`, `mark_redeemed`, `reset_card_to_active`, `get_cards_by_wallet` | ✓ WIRED | All imported and used in the correct order. |
| `tasks.py` | `crud.py` / `services.py` | `_expire_gift_cards` calls `get_expired_active_cards`, `mark_card_expired`, and `reclaim_card_sats` | ✓ WIRED | Imports inside the function avoid circular imports. |
| `__init__.py` | `tasks.py` | `giftcards_start` registers `wait_for_expiry` | ✓ WIRED | `create_permanent_unique_task("ext_giftcards", wait_for_expiry)` is called. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `static/js/redeem.vue` | `giftCard` | `fetch /giftcards/api/v1/cards/public/{token_hash}` | Yes (DB query via `get_card_by_token_hash`) | ✓ FLOWING |
| `static/js/redeem.vue` | `qrCodeUrl` | `window.location.origin` + `/giftcards/api/v1/lnurl/{token_hash}/qr` | Yes (server-side QR endpoint) | ✓ FLOWING |
| `static/js/index.vue` | `giftCards` | `LNbits.api.request GET /giftcards/api/v1/cards` | Yes (DB query via `get_cards_by_wallet`) | ✓ FLOWING |
| `static/js/index.vue` | `createDialog.result` | `LNbits.api.request POST /giftcards/api/v1/cards` | Yes (returns `CreateGiftCardResponse`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Phase 1 test suite | `pytest /home/exedev/giftcards/tests/ -x` | 30 passed in 2.41s | ✓ PASS |
| Concurrency/double-spend test | `pytest /home/exedev/giftcards/tests/test_redemption.py::test_concurrent_redemption_no_double_spend -x` | 1 passed | ✓ PASS |
| Extension module import | `pytest` collection from LNBits root | `from giftcards ...` resolves in test process | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GCARD-01 | 01-01 | Create single gift card with fixed sats amount | ✓ SATISFIED | `CreateGiftCard` model, `api_create_card`, `create_gift_card` service, `index.vue` form. |
| GCARD-02 | 01-01 | Set expiration date at creation | ✓ SATISFIED | `expires_at` field in model, form, and DB. |
| GCARD-03 | 01-01 | Add recipient name, sender name, personal message | ✓ SATISFIED | Fields present in model, form, and public response. |
| GCARD-04 | 01-01 | Unique unguessable redemption token and link | ✓ SATISFIED | `generate_token` + SHA-256; `CreateGiftCardResponse` returns URLs; uniqueness enforced in DB. |
| GCARD-05 | 01-01 | Issuer wallet debited at creation (locked funding) | ✓ SATISFIED | `create_gift_card` calls `update_wallet_balance(wallet=issuer_wallet, amount=-data.amount)`. |
| REDM-01 | 01-01 | Recipient opens link and views value/sender message | ✓ SATISFIED | `api_get_public_card` returns safe public fields; `redeem.vue` renders them. |
| REDM-02 | 01-01 | Recipient redeems by scanning QR with Lightning wallet | ✓ SATISFIED | `lnurl_params` + `lnurl_callback` implement LNURL-withdraw; `lnurl_qr` serves QR code. |
| REDM-03 | 01-02 | Redeem once; concurrent redemption no double-spend | ✓ SATISFIED | Atomic `mark_redeeming` + `test_concurrent_redemption_no_double_spend`. |
| REDM-04 | 01-03 | Expired cards cannot redeem and display expired status | ✓ SATISFIED | Expiry sweep + `lnurl_params`/`lnurl_callback` reject non-active cards; `redeem.vue` expired state. |
| REDM-05 | 01-03 | Expired sats returned to issuer wallet | ✓ SATISFIED | `reclaim_card_sats` + `test_expired_card_reclaims_sats`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No `TODO`, `FIXME`, `XXX`, `TBD`, `HACK`, `PLACEHOLDER`, stub returns, or hardcoded empty data flows found in implementation files. | |

*Note: `redeem.js` line 21 contains a comment explaining that the `lightning:` URI is disabled for Phase 1; this is an intentional Phase 1 limitation, not an unresolved debt marker.*

### Deferred / Phase 2+3 Feature Check

| Feature | Status | Evidence |
|---------|--------|----------|
| Email delivery | Not implemented | No email code in backend or UI. |
| Nostr delivery | Not implemented | No nostr code. |
| Printable/branded card image | Not implemented | Only raw LNURL QR is generated; no templates or composed card image. |
| Bulk creation / CSV | Not implemented | `index.vue` exports CSV but does not import/create in bulk. |
| REST API for external systems | Not implemented | Only issuer endpoints exist; no API key scoping for external automation. |
| Dashboard with filters | Not implemented | Basic card list table only; no status filters. |
| Cancel + manual refund | Not implemented | No cancel endpoint or UI. |
| Audit log | Not implemented | No audit table or logging. |
| Rate limiting | Not implemented | Per D-06, deferred to Phase 6. |

### Human Verification Required

1. **Create a card and verify the issuer wallet is debited.**
   - **Test:** Create a gift card through the issuer UI or via `POST /giftcards/api/v1/cards` and check the issuer wallet balance before and after.
   - **Expected:** The card is created with the requested fields and the issuer wallet balance decreases by the card amount.
   - **Why human:** No automated test exercises the `create_gift_card` service or `api_create_card` endpoint with a real wallet balance assertion.

2. **Open the redemption link and confirm the public page renders correctly.**
   - **Test:** Open the redemption URL in a browser/incognito window.
   - **Expected:** Amount, sender name, personal message, and a scannable QR code are visible and correctly styled.
   - **Why human:** Visual layout and user-facing copy cannot be verified by automated tests.

3. **Scan the QR code with a real Lightning wallet and complete redemption.**
   - **Test:** Scan the LNURL QR code with a Lightning wallet app and confirm the withdrawal.
   - **Expected:** The wallet receives the sats, the card status changes to `redeemed`, and the public page updates to the redeemed state.
   - **Why human:** The full chain from QR generation to wallet scan to LNURL callback requires a real wallet and camera.

### Gaps Summary

No automated gaps remain in the implementation. All Phase 1 requirements are addressed by the code, and the full test suite (30 tests) passes. The only remaining verification is human: the card creation + wallet debit flow, the visual public redemption page, and the end-to-end QR scan redemption have not been exercised by automated tests. Phase 2/3 features are correctly absent.

---

_Verified: 2026-06-29T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
