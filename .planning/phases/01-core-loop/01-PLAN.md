---
phase: 01-core-loop
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - giftcards/__init__.py
  - giftcards/config.json
  - giftcards/description.md
  - giftcards/models.py
  - giftcards/migrations.py
  - giftcards/crud.py
  - giftcards/services.py
  - giftcards/views_api.py
  - giftcards/views.py
  - giftcards/static/js/index.vue
  - giftcards/static/js/redeem.vue
  - giftcards/tests/test_core_loop.py
autonomous: true
requirements:
  - GCARD-01
  - GCARD-02
  - GCARD-03
  - GCARD-04
  - GCARD-05
  - REDM-01
  - REDM-02
user_setup: []
must_haves:
  truths:
    - An issuer can create a funded gift card from the API or UI and receives a unique raw-token redemption link.
    - The issuer wallet is debited by the card amount at creation time.
    - A recipient can open the public redemption link and view the card value and sender message.
    - The recipient can scan the LNURL QR and redeem the sats via Lightning, completing the happy path.
    - The raw token is never stored in the database; only its SHA-256 hash is stored.
  artifacts:
    - path: giftcards/__init__.py
      provides: Extension bootstrap, router assembly, and start/stop lifecycle
      exports: ["db", "giftcards_ext", "giftcards_start", "giftcards_stop", "giftcards_static_files"]
    - path: giftcards/models.py
      provides: Pydantic v1 models for cards, creation input, public response, and summary
      contains: "class GiftCard"
    - path: giftcards/migrations.py
      provides: Initial cards table
      contains: "m001_initial"
    - path: giftcards/crud.py
      provides: Database access and the atomic guard primitives
      contains: "db = Database"
    - path: giftcards/services.py
      provides: Card lifecycle and Lightning funding/payout logic
      contains: "create_gift_card"
    - path: giftcards/views_api.py
      provides: Issuer and public REST + LNURL endpoints
      contains: "api_create_card"
    - path: giftcards/views.py
      provides: SPA routes
      contains: "giftcards_generic_router"
    - path: giftcards/static/js/index.vue
      provides: Issuer UI
      contains: "Create Gift Card dialog"
    - path: giftcards/static/js/redeem.vue
      provides: Public redemption page
      contains: "LNURL QR code"
    - path: giftcards/tests/test_core_loop.py
      provides: Happy-path integration tests
      contains: "test_create_and_redeem_gift_card"
  key_links:
    - from: giftcards/static/js/index.vue
      to: giftcards/views_api.py
      via: "LNbits.api requests to /giftcards/api/v1/cards"
      pattern: "axios|LNbits.api"
    - from: giftcards/static/js/redeem.vue
      to: giftcards/views_api.py
      via: "Fetch public card details and LNURL params"
      pattern: "fetch.*lnurl|public.*token_hash"
    - from: giftcards/views_api.py
      to: giftcards/services.py
      via: "FastAPI handlers call create_gift_card and pay_and_complete"
      pattern: "await create_gift_card|await pay_and_complete"
    - from: giftcards/services.py
      to: "lnbits.core.services.payments"
      via: "update_wallet_balance and pay_invoice"
      pattern: "update_wallet_balance|pay_invoice"
---

## Phase Goal

**As an** LNBits wallet holder, **I want to** create a sats-denominated gift card with a unique secure redemption link and have a recipient redeem it via Lightning, **so that** I can give sats to anyone without manual payout or custodial coordination.

## Acceptance Criteria

- [ ] Issuer can create a gift card with amount, optional expiration, recipient name, sender name, and message.
- [ ] Issuer wallet is debited by the card amount at creation time.
- [ ] The creation response returns the raw token and a shareable redemption URL exactly once.
- [ ] The public redemption page shows the card value and sender message for an active card.
- [ ] The LNURL QR code on the public page triggers a successful Lightning redemption.
- [ ] The raw token is never stored in the database; only the SHA-256 hash is stored.

## Artifacts This Phase Produces

This plan produces the walking skeleton of the extension: a working end-to-end create-and-redeem loop with the extension bootstrap, database schema, Pydantic models, CRUD, service layer, issuer and public API endpoints, LNURL-withdraw endpoints, and both the issuer and public Vue pages. The expiry sweep and concurrency hardening are intentionally deferred to the next two plans in this phase.

<objective>
Prove the full extension stack by delivering the thinnest working end-to-end loop: create a funded gift card, share the unique link, and redeem the sats via LNURL-withdraw.

Purpose: This is the first vertical slice; it exercises the framework, DB, auth, Lightning primitives, and UI together before adding edge-case hardening.
Output: A passing integration test and a manually testable UI for the happy path.
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
@/home/exedev/events/__init__.py
@/home/exedev/events/models.py
@/home/exedev/events/crud.py
@/home/exedev/events/services.py
@/home/exedev/events/views_api.py
@/home/exedev/events/views.py
@/home/exedev/events/static/js/index.vue
@/home/exedev/events/static/js/ticket.vue
@/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write the failing happy-path integration test</name>
  <files>giftcards/tests/test_core_loop.py</files>
  <read_first>
    <file>/home/exedev/events/tests/test_init.py</file>
    <file>/home/exedev/events/views_api.py</file>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-UI-SPEC.md</file>
  </read_first>
  <behavior>
    - Test 1: POST /giftcards/api/v1/cards with an LNBits admin key creates a gift card, returns a 43-character raw token, a redemption URL containing the raw token, and an LNURL URL containing the SHA-256 token hash.
    - Test 2: GET /giftcards/api/v1/cards returns a list of cards for the authenticated wallet but never exposes the token_hash or card_wallet_id fields.
    - Test 3: GET /giftcards/api/v1/lnurl/{token_hash} returns valid LNURL-withdraw JSON with minWithdrawable equal to maxWithdrawable equal to the card amount in millisats.
    - Test 4: GET /giftcards/api/v1/lnurl/callback?pr={valid_bolt11}&k1={token_hash} returns an LnurlSuccessResponse and the card status becomes redeemed.
    - Test 5: The issuer wallet balance decreases by the card amount after creation.
  </behavior>
  <action>
    Create `giftcards/tests/__init__.py` and `giftcards/tests/test_core_loop.py`. Use `pytest` + `pytest-asyncio` and the LNBits `TestClient` pattern from the events extension tests. Import the extension's `create_gift_card` helper and the core wallet/payment primitives. Do NOT implement production code yet; the test should fail because the giftcards package does not exist. Use a real or mocked BOLT11 invoice from the LNBits funding wallet for the redemption callback test. Do not store the raw token in the test assertions beyond what the API returns.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_core_loop.py -x</automated>
  </verify>
  <done>The test file exists and fails with import/no-module errors, confirming the test exercises the expected endpoints before any implementation is written.</done>
  <acceptance_criteria>The test suite covers card creation, issuer list scoping, LNURL params, LNURL callback redemption, and issuer wallet debit; it is committed as the red step of the TDD cycle.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement the backend walking skeleton</name>
  <files>
    giftcards/__init__.py
    giftcards/config.json
    giftcards/description.md
    giftcards/models.py
    giftcards/migrations.py
    giftcards/crud.py
    giftcards/services.py
    giftcards/views_api.py
    giftcards/views.py
  </files>
  <read_first>
    <file>/home/exedev/events/__init__.py</file>
    <file>/home/exedev/events/models.py</file>
    <file>/home/exedev/events/crud.py</file>
    <file>/home/exedev/events/services.py</file>
    <file>/home/exedev/events/views_api.py</file>
    <file>/home/exedev/events/views.py</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
    <file>.planning/phases/01-core-loop/01-RESEARCH.md</file>
    <file>.planning/phases/01-core-loop/01-PATTERNS.md</file>
  </read_first>
  <behavior>
    - The backend must make the tests from Task 1 pass.
    - Card creation must generate a 43-character raw token via `secrets.token_urlsafe(32)`, store only the SHA-256 hash, and return the raw token once in the creation response.
    - The issuer wallet must be debited by the card amount via `update_wallet_balance` before the creation response is returned.
    - The LNURL params endpoint must return a valid `LnurlWithdrawResponse` with `k1` set to the token hash and `minWithdrawable` equal to `maxWithdrawable`.
    - The LNURL callback must validate `k1`, check the card is active, call `pay_invoice` with a valid BOLT11 invoice, and mark the card redeemed on success.
  </behavior>
  <action>
    Create the extension package with the following files, following the events extension patterns and Pydantic v1 rules from RESEARCH.md Pattern 11:

    1. `giftcards/__init__.py`: Define `giftcards_ext` as `APIRouter(prefix="/giftcards", tags=["GiftCards"])`, include `giftcards_api_router` and `giftcards_generic_router`, define `giftcards_static_files`, `giftcards_start`, `giftcards_stop`, and `db` in `__all__`. Keep `giftcards_start` empty of scheduled tasks for this slice (expiry comes in Plan 3).
    2. `giftcards/config.json`: Extension metadata matching the events extension structure.
    3. `giftcards/description.md`: One-sentence description of the extension.
    4. `giftcards/models.py`: Pydantic v1 models `CreateGiftCard`, `GiftCard`, `GiftCardSummary`, `PublicGiftCard`, and `CreateGiftCardResponse`. Use `Optional[X]` for optional fields, `validator` for amount greater than zero, and never include `raw_token` in any model except `CreateGiftCardResponse`.
    5. `giftcards/migrations.py`: `m001_initial` creating `giftcards.cards` with columns matching `GiftCard`, `token_hash` as `TEXT NOT NULL UNIQUE`, and indexes on `wallet` and `(status, expires_at)`. Use `db.timestamp_now` for the default `created_at`.
    6. `giftcards/crud.py`: `db = Database("ext_giftcards")`. Implement `create_card`, `get_card`, `get_card_by_token_hash`, `get_cards_by_wallet` (scoped to the issuer wallet), and an atomic `mark_redeeming(token_hash)` function that executes `UPDATE giftcards.cards SET status = 'redeeming' WHERE token_hash = :hash AND status = 'active'` and returns the card only if `rowcount == 1` per D-08 and STATE.md security-first decision.
    7. `giftcards/services.py`: Implement `generate_token()` returning raw token and SHA-256 hash; `create_gift_card(data, issuer_wallet_id, user_id, base_url)` that checks balance, creates a dedicated card wallet via `create_wallet` (D-03) with a try/except fallback to `card_wallet_id = None` (D-04), inserts the card record, debits the issuer via `update_wallet_balance`, credits the card wallet if created, and returns `CreateGiftCardResponse` with URLs built from `request.base_url`; `pay_and_complete(card, bolt11)` that calls `pay_invoice` with `card_wallet_id` or the issuer wallet as fallback, then marks the card redeemed; and `mark_redeemed` helper using `db.timestamp_placeholder` for `redeemed_at`.
    8. `giftcards/views_api.py`: Create `giftcards_api_router = APIRouter(prefix="/api/v1/cards")` with POST and GET endpoints protected by `require_admin_key`, deriving `wallet.id` and `wallet.user` from the decorator. The POST endpoint returns `CreateGiftCardResponse`. The GET endpoint returns `GiftCardSummary` objects. Add a public endpoint `GET /public/{token_hash}` returning `PublicGiftCard`. Create `giftcards_lnurl_router = APIRouter(prefix="/api/v1/lnurl")` with `GET /{token_hash}` returning `LnurlWithdrawResponse` and `GET /callback` returning `LnurlSuccessResponse` or `LnurlErrorResponse`. Use `parse_obj_as(CallbackUrl, str(request.url_for("giftcards.lnurl_callback")))` for the callback URL. Implement the callback using the atomic `mark_redeeming` CRUD from step 6 per D-08.
    9. `giftcards/views.py`: Create `giftcards_generic_router = APIRouter()` and register `GET /` with `endpoint=index` and `GET /redeem/{raw_token}` with `endpoint=index_public` so LNBits serves the SPA shell for both the issuer page and the public redemption page.

    Honor the locked decisions: use LNURL-withdraw as the redemption primitive (D-01); serve the web page at /redeem/{raw_token} and the LNURL entry point at /api/v1/lnurl/{token_hash} (D-02); keep public endpoints unauthenticated and rely on the unguessable hash for authorization, deferring rate limiting to Phase 6 (D-06, D-12); support states active, redeeming, redeemed, and expired (D-07); namespace tables as giftcards.cards under `lnbits.db.Database("ext_giftcards")` (D-13); and store `token_hash` as a unique indexed column (D-14).

    Do not implement expiry, concurrency stress tests, or payment-failure recovery in this slice; those are Plan 2 and Plan 3. Do not store the raw token or log it. Do not accept `wallet_id` or `user_id` from request bodies.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_core_loop.py -x</automated>
  </verify>
  <done>The backend test suite passes, confirming that an issuer can create a funded card and a recipient can redeem it through the LNURL endpoints.</done>
  <acceptance_criteria>The backend passes all happy-path tests; the list endpoint never exposes token_hash; the LNURL callback uses the atomic status guard; and the raw token is returned only once.</acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire the issuer and public Vue pages</name>
  <files>
    giftcards/static/js/index.vue
    giftcards/static/js/redeem.vue
    giftcards/views_api.py
  </files>
  <read_first>
    <file>/home/exedev/events/static/js/index.vue</file>
    <file>/home/exedev/events/static/js/ticket.vue</file>
    <file>.planning/phases/01-core-loop/01-UI-SPEC.md</file>
    <file>.planning/phases/01-core-loop/01-CONTEXT.md</file>
  </read_first>
  <behavior>
    - The issuer page must render a "Create Gift Card" button, open a dialog with the form fields from the UI-SPEC, submit to the creation endpoint, and display the resulting redemption link with a copy button.
    - The issuer page must list cards created by the authenticated wallet with columns amount, recipient, status, expires, and actions per the UI-SPEC.
    - The public redemption page must read the raw token from the route, hash it to SHA-256 in the browser, call the public card endpoint, and render the active state with amount, sender/message, expiration, and an LNURL QR code.
    - The QR code must be served by the backend from a new endpoint `GET /giftcards/api/v1/lnurl/{token_hash}/qr` returning a PNG, using `pyqrcode` and `PIL` per the events extension QR pattern.
  </behavior>
  <action>
    Create `giftcards/static/js/index.vue` and `giftcards/static/js/redeem.vue` following the UI-SPEC spacing, color, typography, and copywriting contracts. Use Quasar 2 components only and reference theme colors via `color="primary"` and `$q.dark.isActive` patterns from the events extension. Keep the public page mobile-first with minimum 44px touch targets and a 240px/300px QR display.

    In `index.vue`: implement the two-column responsive layout, the create-card dialog with amount, recipient, sender, message, and expiration fields, lazy validation on submit, and a post-creation result panel showing the redemption link with a copy button and the one-time warning from the UI-SPEC. Implement the card list table using `q-table` with `GiftCardSummary` data from `GET /giftcards/api/v1/cards` and status badges colored `positive`, `grey-6`, or `warning`.

    In `redeem.vue`: implement the centered single-column layout, loading spinner, and the active/redeemed/expired/not-found states from the UI-SPEC. Compute the token hash in the browser using `crypto.subtle` (or a bundled SHA-256 helper if available) and call `GET /giftcards/api/v1/cards/public/{token_hash}`. For the active state, render an `img` tag whose `src` is `GET /giftcards/api/v1/lnurl/{token_hash}/qr` and a button linking to the `lightning:` URI if the browser supports it; otherwise rely on the QR image. Add a server-side QR endpoint in `views_api.py` using the events extension QR pattern (PNG with `Cache-Control: no-cache, no-store, must-revalidate`).

    Do not implement email delivery, templates, or bulk UI. Do not use hardcoded hex colors or external CDN resources.
  </action>
  <verify>
    <automated>pytest giftcards/tests/test_core_loop.py -x && python -c "from giftcards import giftcards_ext; print(giftcards_ext.prefix)"</automated>
  </verify>
  <done>Both the issuer page and the public redemption page render and are wired to the backend; the full happy-path test suite still passes.</done>
  <acceptance_criteria>The issuer UI can create a card and copy its link; the public page displays the correct state and LNURL QR; and the e2e integration test remains green.</acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| Issuer browser → API | Authenticated LNBits admin key crosses here; malicious or spoofed requests could create cards against the wrong wallet |
| Public internet → LNURL endpoints | Anyone with the unguessable token hash can call these endpoints; the token hash is the sole authorization |
| Extension → LNBits core | The extension calls `update_wallet_balance`, `pay_invoice`, and `create_wallet` on behalf of the issuer wallet |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T-01-01 | Tampering | `api_create_card` request body | high | mitigate | Derive `wallet_id` and `user_id` from the `require_admin_key` decorator; never accept these from the request body per D-11. |
| T-01-02 | Information Disclosure | `GET /api/v1/cards` response | high | mitigate | Return `GiftCardSummary` model that excludes `token_hash` and `card_wallet_id`; full `GiftCard` is only used internally. |
| T-01-03 | Information Disclosure | Token storage and logs | high | mitigate | Store only the SHA-256 hash of the raw token; return the raw token only in `CreateGiftCardResponse`; do not log it. |
| T-01-04 | Elevation of Privilege | `get_cards_by_wallet` | high | mitigate | Scope all list queries to the `wallet` column equal to `wallet.wallet.id` from the decorator; never return cards owned by another wallet. |
| T-01-05 | Spoofing | Card creation endpoint | high | mitigate | Protect `POST /api/v1/cards` with `require_admin_key`; only a valid LNBits wallet key can create a card. |
| T-01-06 | Information Disclosure | Public card endpoint | high | mitigate | Return only `PublicGiftCard` from `GET /public/{token_hash}`; it excludes `wallet`, `card_wallet_id`, and `token_hash`. |
| T-01-SC | Tampering | Python package installs | high | mitigate | This plan installs no new runtime Python packages; all libraries are already in the LNBits core venv. |

</threat_model>

<verification>
- Run `pytest giftcards/tests/test_core_loop.py -x` and confirm all tests pass.
- Start the LNBits dev server and manually create a card in the issuer UI, then open the redemption link in an incognito window and confirm the card details and LNURL QR are displayed.
- Verify the database contains only the SHA-256 token hash by querying `SELECT token_hash FROM giftcards.cards` and checking the value is a 64-character hex string.
- Verify the list endpoint response does not contain `token_hash` or `card_wallet_id` fields.
</verification>

<success_criteria>
- The integration test `test_core_loop.py` passes and exercises create, list, LNURL params, callback redemption, and wallet debit.
- The issuer page can create a card and display the one-time redemption link.
- The public redemption page shows the correct active state and LNURL QR for a valid raw token.
- No raw token is stored in the database or logs.
- The extension imports cleanly from LNBits (`from giftcards import giftcards_ext`).
</success_criteria>

<output>
Create `.planning/phases/01-core-loop/01-01-SUMMARY.md` when done. Plan 02 depends on this plan's backend files and endpoints.
</output>
