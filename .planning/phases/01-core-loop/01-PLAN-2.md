---
phase: 01-core-loop
plan: 02
type: execute
wave: 2
depends_on:
  - 01-PLAN
files_modified:
  - giftcards/crud.py
  - giftcards/services.py
  - giftcards/views_api.py
  - giftcards/static/js/redeem.vue
  - giftcards/tests/test_redemption.py
autonomous: true
requirements:
  - REDM-03
user_setup: []
must_haves:
  truths:
    - Concurrent redemption attempts cannot result in a double-spend; only the first successful callback marks the card redeemed.
    - If the Lightning payment fails, the card returns to the active state so the recipient can retry.
    - The public redemption page clearly shows already-redeemed and payment-failure states.
    - The LNURL callback validates the k1 token and the BOLT11 invoice before attempting payment.
  artifacts:
    - path: giftcards/crud.py
      provides: Atomic redemption guard and status reset helpers
      contains: "mark_redeeming"
    - path: giftcards/services.py
      provides: Payout and recovery logic
      contains: "pay_and_complete"
    - path: giftcards/views_api.py
      provides: LNURL callback with validation and error responses
      contains: "lnurl_callback"
    - path: giftcards/static/js/redeem.vue
      provides: Redeemed and error UI states
      contains: "redeemed state"
    - path: giftcards/tests/test_redemption.py
      provides: Concurrency and failure tests
      contains: "test_concurrent_redemption_no_double_spend"
  key_links:
    - from: giftcards/views_api.py
      to: giftcards/crud.py
      via: "Atomic mark_redeeming guard before pay_invoice"
      pattern: "mark_redeeming"
    - from: giftcards/views_api.py
      to: giftcards/services.py
      via: "pay_and_complete handles pay_invoice and resets on failure"
      pattern: "pay_and_complete"
    - from: giftcards/services.py
      to: "lnbits.core.services.payments"
      via: "pay_invoice and Payment status check"
      pattern: "pay_invoice"
---

## Phase Goal (continued)

**As an** LNBits wallet holder, **I want to** create a sats-denominated gift card with a unique secure redemption link and have a recipient redeem it via Lightning, **so that** I can give sats to anyone without manual payout or custodial coordination.

## Acceptance Criteria

- [ ] Two simultaneous redemption attempts against the same active card result in exactly one success and one failure response.
- [ ] A failed Lightning payment returns the card to the active state so the recipient can retry with a different wallet.
- [ ] The LNURL callback rejects requests with a missing or mismatched `k1` parameter.
- [ ] The public redemption page displays the redeemed state when the card is already redeemed and an error state when the callback fails.

## Artifacts This Phase Produces

This plan hardens the redemption path: an atomic status guard that prevents concurrent double-spend, callback input validation, and failure recovery that keeps cards redeemable after a transient Lightning failure. It also adds the redeemed and error states to the public redemption page.

<objective>
Make the redemption path safe and recoverable by adding atomic concurrency control, callback validation, and payment-failure recovery.

Purpose: The walking skeleton works for the happy path; this plan ensures the same card cannot be redeemed twice and that a failed payment does not lock the card.
Output: A hardened redemption flow with passing concurrency and failure tests.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-loop/01-CONTEXT.md
@.planning/phases/01-core-loop/01-RESEARCH.md
@.planning/phases/01-core-loop/01-UI-SPEC.md
@.planning/phases/01-core-loop/01-PATTERNS.md
@.planning/phases/01-core-loop/01-PLAN.md
@/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add concurrency and failure tests</name>
  <files>giftcards/tests/test_redemption.py</files>
  <read_first>
    <file>giftcards/tests/test_core_loop.py</file>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
  </read_first>
  <behavior>
    - Test 1: Two concurrent LNURL callback requests for the same active card with different valid BOLT11 invoices result in exactly one `LnurlSuccessResponse` and one `LnurlErrorResponse`; the card ends in `redeemed` status.
    - Test 2: A callback with a mismatched `k1` parameter returns an `LnurlErrorResponse` and does not change the card status.
    - Test 3: A callback with a missing `pr` parameter returns an `LnurlErrorResponse` and does not change the card status.
    - Test 4: When `pay_invoice` raises `PaymentError`, the callback returns an `LnurlErrorResponse` and the card status returns to `active` so a retry is possible.
    - Test 5: When `pay_invoice` returns a payment with `PENDING` status, the callback returns an `LnurlErrorResponse` and the card status returns to `active`.
  </behavior>
  <action>
    Create `giftcards/tests/test_redemption.py` with the above tests. Use `asyncio.gather` or `pytest-asyncio` concurrency for the double-spend test. Use `unittest.mock` to simulate `PaymentError` and a pending `Payment` status. The tests should initially fail because the callback does not yet implement atomic locking or failure recovery.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_redemption.py -x</automated>
  </verify>
  <done>The test file exists and fails as expected because the callback is not yet hardened.</done>
  <acceptance_criteria>The test suite covers concurrent double-spend, missing/mismatched k1, missing invoice, payment error, and pending payment recovery.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Harden the LNURL callback with atomic guard and failure recovery</name>
  <files>
    giftcards/crud.py
    giftcards/services.py
    giftcards/views_api.py
  </files>
  <read_first>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-PATTERNS.md</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
    <file>/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py</file>
  </read_first>
  <behavior>
    - The callback must use the atomic `mark_redeeming(token_hash)` CRUD function: an `UPDATE ... WHERE token_hash = :hash AND status = 'active'` that returns the card only if `rowcount == 1`.
    - If the atomic guard returns `None`, the callback must return `LnurlErrorResponse(reason="Gift card is not available for redemption")`.
    - If `pay_invoice` raises `PaymentError` or any exception, or returns a payment with `PENDING` status, the callback must call `reset_card_to_active(card_id)` and return `LnurlErrorResponse` with a generic reason.
    - On success, the card must be marked `redeemed` with `redeemed_at` set via `db.timestamp_placeholder` and the callback returns `LnurlSuccessResponse`.
  </behavior>
  <action>
    Update the redemption flow in the backend:

    1. In `giftcards/crud.py`, ensure `mark_redeeming(token_hash)` performs the atomic update inside `db.connect()` and returns `None` if no row is changed. Add `reset_card_to_active(card_id)` and `mark_redeemed(card_id)` helpers that use `db.timestamp_placeholder('now')` with a float timestamp value.
    2. In `giftcards/services.py`, refactor `pay_and_complete(card, bolt11)` to return the `Payment` object. If `pay_invoice` raises `PaymentError` or any exception, re-raise it so the caller can reset the card. If the returned `Payment.status` is `PENDING` (or any non-success state), raise a clear exception so the caller resets the card.
    3. In `giftcards/views_api.py`, rewrite `lnurl_callback` to: validate `k1` and `pr` are present; call `mark_redeeming(k1)`; if it returns `None`, return `LnurlErrorResponse`; otherwise call `pay_and_complete(card, pr)` inside a try/except; on any exception, call `reset_card_to_active(card.id)` and return `LnurlErrorResponse` with a generic reason; on success, call `mark_redeemed(card.id)` and return `LnurlSuccessResponse`. Do not expose the raw token or internal exception details in the response.

    Keep the existing LNURL params endpoint unchanged. This hardening follows the LNURL-withdraw primitive decision (D-01) and the failure recovery requirement (D-15). Do not add expiry logic here; that is Plan 3.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_redemption.py -x</automated>
  </verify>
  <done>The atomic guard and failure recovery tests pass; the callback correctly handles concurrent and failed redemptions.</done>
  <acceptance_criteria>The callback uses atomic `mark_redeeming`; only one concurrent request wins; failures reset the card to active; and error responses never leak the raw token or internal exception details.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Render redeemed and error states in the public page</name>
  <files>
    giftcards/static/js/redeem.vue
  </files>
  <read_first>
    <file>giftcards/static/js/redeem.vue</file>
    <file>.planning/phases/01-core-loop/01-UI-SPEC.md</file>
  </read_first>
  <behavior>
    - When the public endpoint returns `status == "redeemed"`, the page must show the redeemed state with the check icon and message from the UI-SPEC copywriting contract.
    - When the LNURL callback returns an error (e.g., after a payment failure), the page must display the error state with the warning icon and retry guidance.
    - The active state must still display the LNURL QR and the redeem button.
  </behavior>
  <action>
    Update `giftcards/static/js/redeem.vue` to implement the State B (already redeemed), State C (expired), and State D (not found) layouts from the UI-SPEC. For State E (error after a failed callback), add a new state card using the negative icon and the UI-SPEC error copy "Redemption failed. Please scan the QR code again or try a different wallet." Ensure the page does not reload automatically; the recipient must manually scan again. Use the same color and icon-only-with-aria-label rules as the active state.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_redemption.py -x && pytest giftcards/tests/test_core_loop.py -x</automated>
  </verify>
  <done>The public page renders the correct state for redeemed, expired, not-found, and callback-error scenarios without regressing the happy path.</done>
  <acceptance_criteria>The public page handles all four status states and a callback error state; existing happy-path tests remain green.</acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| Public internet → LNURL callback | Anyone with the token hash can call `GET /callback`; the request must be validated and the card state must be protected against race conditions |
| Extension → LNBits payments | `pay_invoice` may fail or time out; the extension must recover without losing the card |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T-02-01 | Denial of Service / Double-spend | `lnurl_callback` | high | mitigate | Use atomic `UPDATE ... WHERE status = 'active'` in `mark_redeeming`; only proceed if `rowcount == 1`; all other concurrent requests receive `LnurlErrorResponse`. |
| T-02-02 | Tampering | `lnurl_callback` parameters | medium | mitigate | Reject requests with missing `pr` or `k1`, and reject `k1` values that do not match the expected token hash. |
| T-02-03 | Repudiation | `lnurl_callback` stuck state | high | mitigate | Catch `PaymentError` and any unexpected exception; call `reset_card_to_active` before returning `LnurlErrorResponse`. Also inspect the returned `Payment` status and reset if it is `PENDING`. |
| T-02-04 | Information Disclosure | `LnurlErrorResponse` reason | low | accept | Return a generic user-facing reason; log the full exception server-side with `loguru` without including the raw token. |
| T-02-05 | Denial of Service | Retry storm | low | accept | Phase 1 defers rate limiting; the atomic guard and active-state reset already bound the damage to one attempt per valid invoice per card. |
| T-02-SC | Tampering | Python package installs | high | mitigate | This plan installs no new runtime Python packages. |

</threat_model>

<verification>
- Run `pytest giftcards/tests/test_redemption.py -x` and confirm all concurrency and failure tests pass.
- Run the full Phase 1 test suite `pytest giftcards/tests/` to ensure no regressions.
- Manually trigger two rapid redemption attempts against the same card and confirm one succeeds and one returns an error in the wallet.
- Check that after a failed payment (e.g., with an invalid invoice), the card status returns to `active` in the database.
</verification>

<success_criteria>
- Concurrent redemption attempts result in exactly one success and one failure, with the final card status being `redeemed`.
- `pay_invoice` failures and pending payments return the card to `active` and the callback returns an error response.
- The public page displays the redeemed and error states per the UI-SPEC.
- No raw token or internal stack trace is exposed in LNURL error responses.
</success_criteria>

<output>
Create `.planning/phases/01-core-loop/01-02-SUMMARY.md` when done. Plan 03 depends on this plan's backend files and the active/redeemed status machine.
</output>
