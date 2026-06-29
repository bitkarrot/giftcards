---
phase: 01-core-loop
plan: 03
type: execute
wave: 3
depends_on:
  - 01-PLAN-2
files_modified:
  - giftcards/__init__.py
  - giftcards/crud.py
  - giftcards/services.py
  - giftcards/tasks.py
  - giftcards/static/js/redeem.vue
  - giftcards/tests/test_expiry.py
  - giftcards/tests/test_security.py
autonomous: true
requirements:
  - REDM-04
  - REDM-05
user_setup: []
must_haves:
  truths:
    - Gift cards with a past expiration date are automatically marked expired and cannot be redeemed.
    - Sats from expired cards are returned to the issuer wallet.
    - The public redemption page shows the expired state for an expired card.
    - Security tests confirm that raw tokens are never stored, token hashes are not exposed in list responses, and cross-wallet access is denied.
  artifacts:
    - path: giftcards/tasks.py
      provides: Background expiry sweep registration
      contains: "wait_for_expiry"
    - path: giftcards/crud.py
      provides: Expiry query and atomic mark-expired helper
      contains: "get_expired_active_cards"
    - path: giftcards/services.py
      provides: Sats reclaim logic
      contains: "reclaim_card_sats"
    - path: giftcards/__init__.py
      provides: Task lifecycle wiring
      contains: "giftcards_start"
    - path: giftcards/static/js/redeem.vue
      provides: Expired state UI
      contains: "expired state"
    - path: giftcards/tests/test_expiry.py
      provides: Expiry sweep tests
      contains: "test_expired_card_reclaims_sats"
    - path: giftcards/tests/test_security.py
      provides: Security acceptance tests
      contains: "test_token_hash_not_in_list_response"
  key_links:
    - from: giftcards/tasks.py
      to: giftcards/crud.py
      via: "wait_for_expiry calls get_expired_active_cards"
      pattern: "get_expired_active_cards"
    - from: giftcards/tasks.py
      to: giftcards/services.py
      via: "wait_for_expiry calls reclaim_card_sats"
      pattern: "reclaim_card_sats"
    - from: giftcards/__init__.py
      to: giftcards/tasks.py
      via: "giftcards_start registers wait_for_expiry"
      pattern: "create_permanent_unique_task"
    - from: giftcards/services.py
      to: "lnbits.core.services.payments"
      via: "update_wallet_balance reclaims sats"
      pattern: "update_wallet_balance"
---

## Phase Goal (continued)

**As an** LNBits wallet holder, **I want to** create a sats-denominated gift card with a unique secure redemption link and have a recipient redeem it via Lightning, **so that** I can give sats to anyone without manual payout or custodial coordination.

## Acceptance Criteria

- [ ] A card past its expiration date is marked `expired` by the background sweep and cannot be redeemed through the LNURL callback.
- [ ] The issuer wallet is credited with the card amount when an expired card is reclaimed.
- [ ] The public redemption page shows the expired state with the correct message from the UI-SPEC.
- [ ] Security tests confirm the token hash is never returned in list or public responses, the raw token is never stored, and cross-wallet access is blocked.

## Artifacts This Phase Produces

This plan completes the Phase 1 core loop by adding automatic expiration, sats reclaim, and a security review. It produces the background expiry task, the reclaim service, the expired UI state, and a focused security test suite that verifies the locked decisions from CONTEXT.md.

<objective>
Close the Phase 1 loop by adding automatic expiry, sats reclaim, and a security acceptance test suite.

Purpose: Unclaimed cards must return their locked sats to the issuer, and the implementation must prove it honors the security decisions from CONTEXT.md.
Output: Passing expiry and security tests, plus a registered background sweep task.
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
@.planning/phases/01-core-loop/01-PLAN-2.md
@/home/exedev/events/tasks.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add failing expiry and security tests</name>
  <files>
    giftcards/tests/test_expiry.py
    giftcards/tests/test_security.py
  </files>
  <read_first>
    <file>giftcards/tests/test_core_loop.py</file>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
  </read_first>
  <behavior>
    - Expiry test 1: A card with an `expires_at` in the past is returned by `get_expired_active_cards` and is marked `expired` after the sweep runs; the LNURL callback then returns an error.
    - Expiry test 2: After the sweep, the issuer wallet balance increases by the card amount and the card wallet balance decreases by the same amount (or the issuer wallet is credited if the fallback model was used).
    - Security test 1: `GET /api/v1/cards` never contains `token_hash` or `card_wallet_id` in its JSON response.
    - Security test 2: The database row contains only the SHA-256 hash; no column stores the raw token.
    - Security test 3: A wallet with a different LNBits admin key cannot list or redeem cards created by another wallet.
    - Security test 4: The public endpoint returns only the safe `PublicGiftCard` fields; `wallet`, `card_wallet_id`, and `token_hash` are absent.
  </behavior>
  <action>
    Create `giftcards/tests/test_expiry.py` and `giftcards/tests/test_security.py`. Use the existing test utilities to create cards with explicit past expiration dates. For the sweep test, call the sweep function directly in the test rather than waiting for the background interval. Assert on wallet balances and card status. For the security tests, inspect JSON responses and database rows. The tests should fail initially because the expiry task and security guards are not yet implemented or tested.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_expiry.py -x && pytest giftcards/tests/test_security.py -x</automated>
  </verify>
  <done>Both test files exist and fail as expected because the expiry and security assertions are not yet satisfied.</done>
  <acceptance_criteria>The expiry test suite covers sweep marking, reclaim, and callback rejection; the security test suite covers token hash exposure, raw token storage, and cross-wallet isolation.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement the expiry sweep and sats reclaim</name>
  <files>
    giftcards/crud.py
    giftcards/services.py
    giftcards/tasks.py
    giftcards/__init__.py
    giftcards/static/js/redeem.vue
  </files>
  <read_first>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-PATTERNS.md</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
    <file>/home/exedev/events/tasks.py</file>
  </read_first>
  <behavior>
    - The background sweep must find all cards with `status = 'active'`, non-null `expires_at`, and `expires_at < now` using `db.timestamp_placeholder('now')` with a float timestamp.
    - For each expired card, the sweep must atomically update `status = 'expired'` and `expired_at = now` only if the card is still `active`.
    - The sweep must then reclaim the card amount from the dedicated card wallet back to the issuer wallet via `update_wallet_balance`. If `card_wallet_id` is None, the sweep credits the issuer wallet directly because the issuer wallet was not actually debited separately in the fallback model (or simply records the reclaim if the dedicated wallet path was used).
    - The LNURL params and callback endpoints must return `LnurlErrorResponse` for any card whose status is not `active`.
    - The public redemption page must display the expired state from the UI-SPEC.
  </behavior>
  <action>
    Implement the expiry and reclaim subsystem:

    1. In `giftcards/crud.py`, add `get_expired_active_cards()` that queries `WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at < :now` using `db.timestamp_placeholder('now')`. Add `mark_card_expired(card_id)` that executes `UPDATE giftcards.cards SET status = 'expired', expired_at = :now WHERE id = :id AND status = 'active'` and checks `rowcount`. Add `get_card_by_id(id)` if not already present.
    2. In `giftcards/services.py`, add `reclaim_card_sats(card: GiftCard)`. If `card_wallet_id` exists, fetch both wallets and move the amount via `update_wallet_balance(card_wallet, -amount)` followed by `update_wallet_balance(issuer_wallet, +amount)`. If `card_wallet_id` is None, credit the issuer wallet directly. Wrap the reclaim in try/except and log errors with `loguru` without exposing the raw token.
    3. In `giftcards/tasks.py`, add `_expire_gift_cards()` that iterates over `get_expired_active_cards()`, calls `mark_card_expired`, and then `reclaim_card_sats`. Add `wait_for_expiry()` that returns `run_interval(60, _expire_gift_cards)()` per D-09 and D-10. Import inside the functions to avoid circular imports at module load time.
    4. In `giftcards/__init__.py`, update `giftcards_start()` to register the sweep with `create_permanent_unique_task("ext_giftcards", wait_for_expiry)` and `giftcards_stop()` to cancel all scheduled tasks. Keep the `scheduled_tasks` list.
    5. In `giftcards/static/js/redeem.vue`, add the expired state from the UI-SPEC using the warning icon and the message "The card expired on {date}. The sats have been returned to the issuer."
    6. Update the LNURL params and callback handlers to reject any card whose status is not `active` with `LnurlErrorResponse`.

    Do not add audit logs, cancel flow, or rate limiting in this slice. Keep the DB transaction short: do not hold a connection across `update_wallet_balance` calls.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_expiry.py -x</automated>
  </verify>
  <done>The expiry sweep and reclaim tests pass; expired cards are marked, their sats are reclaimed, and the LNURL endpoints reject them.</done>
  <acceptance_criteria>The background sweep runs every 60 seconds, marks expired cards atomically, reclaims sats to the issuer wallet, and the public page shows the expired state.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Run the security acceptance review and fix any gaps</name>
  <files>
    giftcards/models.py
    giftcards/crud.py
    giftcards/views_api.py
    giftcards/tests/test_security.py
  </files>
  <read_first>
    <file>giftcards/tests/test_security.py</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
  </read_first>
  <behavior>
    - The security test suite from Task 1 must pass without modification.
    - Any failing test must be addressed by a concrete code change, not by weakening the test.
    - The threat model register for this plan must be updated to reflect the actual mitigations implemented.
  </behavior>
  <action>
    Run the security tests. If any fail, fix the root cause:
    - If `token_hash` or `card_wallet_id` appears in the list response, switch to `GiftCardSummary` or add a response model.
    - If the database stores the raw token anywhere, remove the column or write path.
    - If the public endpoint exposes `wallet` or `card_wallet_id`, tighten the `PublicGiftCard` response model.
    - If a cross-wallet test passes unexpectedly, add an explicit `wallet = :wallet` filter to the CRUD list query and verify the decorator is applied.
    - Add negative greps to the automated verification to ensure `token_hash` is not present in the `GET /api/v1/cards` response schema and `raw_token` is not present in any database column.

    Do not add new features; only close security gaps and verify the existing locked decisions from CONTEXT.md.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_security.py -x && pytest giftcards/tests/ -x</automated>
  </verify>
  <done>All security tests pass, the full Phase 1 test suite passes, and no raw token or token hash is leaked.</done>
  <acceptance_criteria>The security test suite passes; the full Phase 1 test suite passes; the threat model register accurately reflects implemented mitigations.</acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| Extension background task → DB | The periodic expiry sweep has privileged access to change card status and trigger reclaim payments |
| Expired card → issuer wallet | Sats must move only from the correct card wallet back to the correct issuer wallet |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T-03-01 | Tampering | `mark_card_expired` | medium | mitigate | Use `UPDATE ... WHERE id = :id AND status = 'active'` and verify `rowcount == 1` so only active cards can become expired. |
| T-03-02 | Repudiation | `reclaim_card_sats` | medium | mitigate | Reclaim only from the card's `card_wallet_id` to the issuer wallet; log failures but do not silently skip reclaim. |
| T-03-03 | Information Disclosure | Expired public response | low | mitigate | Return only `PublicGiftCard` fields; never expose `wallet`, `card_wallet_id`, or `token_hash`. |
| T-03-04 | Denial of Service | Background task crash | medium | mitigate | Register the sweep with `create_permanent_unique_task("ext_giftcards", wait_for_expiry)` so it restarts on crash; cancel it cleanly in `giftcards_stop`. |
| T-03-05 | Elevation of Privilege | Reclaim to wrong wallet | medium | mitigate | Use the `card.wallet` issuer wallet ID recorded at creation time; do not derive it from request parameters. |
| T-03-06 | Information Disclosure | `expires_at` precision | low | accept | The public page shows the expiration date; this is a user-facing feature and does not expose secrets. |
| T-03-SC | Tampering | Python package installs | high | mitigate | This plan installs no new runtime Python packages. |

</threat_model>

<verification>
- Run `pytest giftcards/tests/test_expiry.py -x` and confirm expiry marking, reclaim, and callback rejection pass.
- Run `pytest giftcards/tests/test_security.py -x` and confirm no raw token or token hash leakage and no cross-wallet access.
- Run the full Phase 1 suite `pytest giftcards/tests/ -x` and confirm all tests pass.
- Verify the `giftcards_start()` function registers the expiry task and `giftcards_stop()` cancels it.
- Manually create a card with an expiration in the past, wait for the sweep, and confirm the card page shows the expired state.
</verification>

<success_criteria>
- Expired cards are automatically marked `expired` by the background sweep and their sats are returned to the issuer wallet.
- The LNURL endpoints reject expired cards.
- The public page shows the expired state per the UI-SPEC.
- Security tests pass: no raw token stored, no token_hash in list/public responses, no cross-wallet access.
- The full Phase 1 test suite is green.
</success_criteria>

<output>
Create `.planning/phases/01-core-loop/01-03-SUMMARY.md` when done. This is the final plan of Phase 1; the phase is ready for transition after all three SUMMARYs are written.
</output>
