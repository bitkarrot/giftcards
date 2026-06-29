# Project Research Summary

**Project:** LNBits Gift Cards Extension
**Domain:** LNBits extension — Lightning Network sats-denominated gift cards (create, fund, distribute, redeem)
**Researched:** 2026-06-29
**Confidence:** MEDIUM (stack HIGH, architecture MEDIUM, features MEDIUM, pitfalls MEDIUM)

## Executive Summary

This project is a LNBits extension that implements a complete gift card lifecycle — issuance, branded image generation, email/delivery, and LNURL-withdraw redemption — as a FastAPI `APIRouter` mounted inside the LNBits v1.5.4 ASGI application. The canonical pattern for this type of extension is well-established: thin HTTP routers delegate to a `services.py` business-logic layer which coordinates a pure-I/O `crud.py` layer backed by `lnbits.db.Database`. No new runtime Python dependencies are needed; Pillow, pyqrcode, httpx, and SMTP primitives are already present in the LNBits core dependency set. The frontend is a Vue 3 + Quasar SPA served as `.vue` files with no build step required.

The recommended approach is a staged build starting with the secure data model and extension scaffold (token hashing, migration namespacing, ownership enforcement), progressing to the core LNURL-withdraw redemption loop, then layering image generation and email delivery on top, and finally adding bulk CSV and the admin dashboard as a polish layer. This ordering is enforced by hard architectural dependencies: the LNURL-withdraw callback URL is baked into every QR code at creation time, so the URL structure must be finalised before any card is issued; and the atomic redemption guard must be in place before any LNURL-withdraw endpoint goes live.

The primary risks are security-structural and must be resolved in Phase 1 or they require a complete rewrite: predictable/plaintext tokens (use `secrets.token_urlsafe(32)`, store SHA-256 hash only), missing wallet-ownership scoping on admin endpoints (always derive wallet from `require_admin_key`, never from request body), and double-spend race conditions at redemption (single atomic `UPDATE … WHERE redeemed = false`). A secondary execution risk is synchronous bulk/image/email work blocking the async event loop; this must be offloaded to `asyncio.to_thread` and background tasks before any realistic load. None of these risks require external dependencies or architectural changes if addressed in the correct phase.

---

## Key Findings

### Recommended Stack

LNBits extensions are first-class FastAPI `APIRouter` instances — no standalone server, no new framework, and no new runtime dependencies unless merged into LNBits core `pyproject.toml`. The entire extension runs on the existing LNBits Python 3.10–3.12 environment pinned to FastAPI ~0.116.1, Pydantic **v1** (~1.10.26, not v2), and SQLAlchemy ~1.4.54 with `lnbits.db.Database` as the abstraction layer for both SQLite (dev) and PostgreSQL (prod).

For gift-card-specific functionality: Pillow ~12.1.0 for image compositing and pyqrcode ~1.2.1 for QR matrix generation are both already in LNBits core. Email delivery reuses `settings.lnbits_email_notifications_*` SMTP settings via a custom `MIMEMultipart` builder (the core `send_email_notification` helper does not support image attachments). Bulk CSV parsing uses stdlib `csv.DictReader`; token generation uses stdlib `secrets.token_urlsafe(32)`.

**Core technologies:**
- **FastAPI `APIRouter` / Starlette ~0.47.1**: Extension HTTP layer — extensions are routers registered by LNBits core, not standalone apps
- **Pydantic ~1.10.26 (v1)**: Models and validation — v2 is incompatible with LNBits 1.5.x; mixing breaks serialization
- **`lnbits.db.Database("ext_giftcards")`**: DB access — abstracts SQLite/PostgreSQL; all tables must be namespaced `ext_giftcards.*`
- **Pillow ~12.1.0 + pyqrcode ~1.2.1**: Image compositing — QR matrix drawn onto template PNG/JPEG; must run in `asyncio.to_thread()` (CPU-bound)
- **`lnbits.core.services.payments.pay_invoice`**: Redemption payout — pays recipient's Lightning wallet when card is redeemed
- **Vue 3 + Quasar (bundled in LNBits core)**: Issuer dashboard and public redemption page — `.vue` files served without a build step
- **`secrets` + `hashlib` (stdlib)**: Token security — generate `secrets.token_urlsafe(32)`, store SHA-256 hash only
- **`smtplib` + `email.mime` (stdlib)**: Email delivery — reuse LNBits SMTP settings; `MIMEMultipart` for image attachments

**Do not use:** Pydantic v2, Flask/Quart/Django, Celery/Redis, pandas, `uuid4` or short hashes as redemption secrets, client-side QR generation, plaintext token storage.

### Expected Features

Research cross-referenced LNBits LNURL-withdraw, Lightning TipCards, Azteco, ZBD Vouchers, btc-giftcard, and the BHN/NAPCO 2025 Digital Gift Card Programs benchmark (100 programs). The key market gap: no existing Lightning-native product combines email delivery with branded image, CSV bulk import with per-recipient variable amounts, design templates, expiry enforcement, and an issuer dashboard. This extension fills all of that.

**Must have (table stakes) — v1 launch:**
- **Single gift card creation + LNURL-withdraw redemption link/QR** — the atomic unit; everything else builds on this
- **Fixed sats amount + sender name + message** — personalization is universally expected, low cost
- **Single-use enforcement** — atomic DB update; prevents double-spend
- **Expiration date enforcement + automatic sats reclaim** — industry standard; no competing LN product offers this
- **Email delivery with card image attachment** — explicit project requirement; primary distribution channel; async task (do not block creation)
- **Issuer dashboard with card status list** — status states: `created → active → redeemed / expired / cancelled`
- **Bulk creation from form (same amount, N cards)** — low complexity; fast win for event/holiday use
- **At least 2 design templates with configurable QR placement** — makes it feel like a product, not a prototype
- **REST API: create card, get card status** — explicit project requirement; enables automation

**Should have (competitive differentiators) — v1.x:**
- **CSV bulk upload with per-recipient variable amounts** — no Lightning-native competitor offers this; unlocks enterprise/event use cases
- **Printable PNG/PDF download** — complement to email; physical gifting use case
- **Per-card audit log** — every create/email/view/redeem/expire/cancel event with timestamp
- **Cancel + manual refund flow** — issuer invalidates card pre-expiry; sats returned to issuer wallet

**Defer (v2+):**
- **Nostr npub delivery (NIP-04/NIP-17 DM)** — Bitcoin-native channel; defer until email delivery stable
- **SMS delivery** — requires external provider (Twilio/Vonage); out of scope for v1
- **NFC / Bolt Card integration** — physical card companion; LNBits Bolt Cards extension already exists

**Anti-features (do not implement):**
- Partial spend / balance-preserving redemption — full-amount single-use only; partial spend requires custodial accounting
- Fiat denomination storage — show approximate fiat at creation time only, read from LNBits rate endpoint, never store
- Real-time WebSocket push for dashboard — polling is sufficient; websockets add complexity with no recipient benefit

### Architecture Approach

The extension follows the canonical LNBits extension layering: `views_api.py` (thin auth + input validation) → `services.py` (business logic, lifecycle orchestration, image generation, email delivery) → `crud.py` (pure DB I/O, no business logic) → `lnbits.db.Database`. Background work lives in `tasks.py` (invoice listener, WebSocket payment push). The Vue SPA frontend is split into `static/js/index.vue` (issuer dashboard, admin-key auth) and `static/js/redeem.vue` (public guest page, no auth). Public endpoints (LNURL-withdraw callbacks, QR image endpoints, redemption page) require no authentication; all issuer mutations use `require_admin_key`.

The LNURL-withdraw redemption pattern (pull-based: recipient wallet initiates payment, extension pays out via `pay_invoice`) prevents failed pushes to offline wallets and requires no LNBits account for recipients. The atomic redemption guard — a single `UPDATE … WHERE redeemed = false AND expired = false` with rowcount check — is the only safe way to prevent double-spend under concurrent requests.

**Major components:**
1. **`__init__.py`** — Extension bootstrap: register routers, static files, start/stop lifecycle hooks; register background task
2. **`models.py`** — Pydantic domain models: `GiftCard`, `Batch`, `CreateGiftCard`, `RedeemRequest`, `PublicGiftCard`
3. **`migrations.py`** — Sequential, idempotent DB migrations; tables namespaced as `ext_giftcards.*`; compatible with SQLite and PostgreSQL
4. **`crud.py`** — Pure DB I/O: `create_card`, `get_card_by_token`, `mark_redeemed_atomic`, `update_card`, `expire_card`
5. **`services.py`** — Business logic: card lifecycle transitions, image generation (`asyncio.to_thread` + Pillow), email delivery (MIMEMultipart), LNURL-withdraw creation
6. **`views_api.py`** — REST + WebSocket endpoints: issuer endpoints (`require_admin_key`), public LNURL-withdraw callbacks and QR image endpoints (no auth)
7. **`tasks.py`** — Invoice listener (`register_invoice_listener`), per-payment-hash WebSocket queues; all wrapped in `try/except`
8. **`static/js/index.vue`** — Admin/issuer dashboard SPA (Vue 3 + Quasar)
9. **`static/js/redeem.vue`** — Public redemption page (guest, no LNBits account required)
10. **`static/image/`** — Template PNG/JPEG backgrounds (giftcard, christmas, birthday at minimum)

### Critical Pitfalls

Research identified 7 critical pitfalls; the top 5 most impactful are:

1. **Predictable or weak redemption tokens** — Use `secrets.token_urlsafe(32)` (≥128 bits CSPRNG), store only SHA-256 hash in DB, return raw token only once at creation. Address in **Phase 1**; changing token format invalidates all issued cards.

2. **Double-spend race condition at redemption** — Use a single atomic DB `UPDATE … WHERE redeemed = false` and check rowcount == 1 before calling `pay_invoice`. Never use read-check-write sequence. Address in **Phase 3**; the most dangerous operational phase.

3. **Plaintext token storage / log exposure** — Never store the raw token; store its SHA-256 hash. Mask tokens in logs. Do not expose tokens in list endpoints, exports, or admin dashboard. Address in **Phase 1**; data model changes are irreversible after cards are issued.

4. **Missing wallet-ownership authorization** — Every issuer endpoint must use `require_admin_key` and scope all DB queries to `wallet.id` derived from the decorator — never from request body. Verify with cross-wallet access tests. Address in **Phases 1 and 5**.

5. **Synchronous bulk/image/email work blocking the event loop** — All Pillow/QR rendering must use `asyncio.to_thread()`; CSV parsing and email sends must be enqueued as background tasks; bulk endpoints return a job ID immediately. Address in **Phase 4** (and verify with 500-row CSV load test).

---

## Implications for Roadmap

Based on combined research, the natural build order is driven by three hard constraints:
1. The LNURL-withdraw callback URL is baked into QR codes at creation — URL structure must be final before any card is issued
2. Security foundations (token hashing, ownership checks) cannot be retrofitted after cards are live
3. Image generation and email delivery depend on a working single-card creation loop

### Phase 1: Foundation — Secure Scaffold, Data Model, Extension Bootstrap

**Rationale:** Three of the seven critical pitfalls (weak tokens, plaintext storage, missing auth) must be resolved here — they are irreversible once any card is issued. The LNURL-withdraw URL structure must also be locked in. This phase has zero Lightning payment complexity but determines security correctness for all later phases.
**Delivers:** Working LNBits extension skeleton with correct file structure, namespaced DB migrations, hashed-token data model, and stub API endpoints with proper auth enforcement
**Addresses features:** Extension scaffold, `config.json`, `models.py`, `migrations.py`, `crud.py` stubs, auth enforcement pattern
**Avoids pitfalls:** Weak tokens (Pitfall 1), plaintext storage (Pitfall 3), missing ownership checks (Pitfall 2), non-namespaced tables / new dependencies (Pitfall 7)
**Research flag:** Standard LNBits patterns — skip deep research phase; use events extension as direct reference

### Phase 2: Core Card API — Create, Fund, Lifecycle

**Rationale:** Establishes the single-card creation loop and state machine before any redemption or delivery work. Funding model (direct wallet debit vs. pay-invoice roundtrip) must be decided here; research recommends direct debit as simpler. No external integrations needed.
**Delivers:** `POST /api/v1/cards` endpoint (admin_key), card state machine (`created → active → expired`), wallet balance check, `tasks.py` invoice listener skeleton, basic `GET /api/v1/cards` list (wallet-scoped)
**Uses:** `lnbits.db.Database`, `lnbits.core.services.payments`, Pydantic v1 models, `register_invoice_listener`
**Implements:** `services.py::create_gift_card`, `crud.py` full implementation, `tasks.py` bootstrap
**Research flag:** Standard patterns — no additional research needed; direct reference to events extension

### Phase 3: Redemption — LNURL-Withdraw, Atomic Guard, Expiry

**Rationale:** This is the highest-risk phase (Pitfall 4: double-spend) and must be isolated for focused testing. The LNURL-withdraw callback URL structure is finalised here — this is the "point of no return" for QR code design. Expiry background task is included because it is tightly coupled to the redemption state machine.
**Delivers:** LNURL-withdraw params endpoint, atomic redemption callback, expiry background task with sats reclaim, redemption page stub (`redeem.vue`)
**Addresses features:** LNURL-withdraw redemption, single-use enforcement, expiration date enforcement, automatic sats reclaim, guest/walletless redemption
**Avoids pitfalls:** Race condition / double-spend (Pitfall 4), lifecycle gaps / stuck-in-redeeming (Pitfall 5)
**Research flag:** Needs research phase — Lightning payment failure/retry handling and hold-invoice options are nuanced; recommend `/gsd-plan-phase --research-phase 3` before implementation

### Phase 4: Image Generation + Email Delivery

**Rationale:** Depends on a working card creation loop (Phase 2) but is fully independent of redemption internals. Image rendering is CPU-bound and must use `asyncio.to_thread` from the start to avoid event loop blocking. Email delivery is async-only. This phase delivers the primary user-visible product value (branded cards).
**Delivers:** Pillow + pyqrcode card image compositing, design template system (2–3 templates), email delivery with MIMEMultipart image attachment, async background task for image+email, QR image endpoint (`/api/v1/cards/{id}/image`)
**Uses:** Pillow ~12.1.0, pyqrcode ~1.2.1, `smtplib` + `email.mime` (stdlib), `asyncio.to_thread`, `MIMEMultipart`
**Avoids pitfalls:** Synchronous bulk/image/email blocking event loop (Pitfall 6)
**Research flag:** Standard patterns — PIL compositing and SMTP are well-documented; no additional research needed

### Phase 5: Bulk Creation, CSV Upload, Admin Dashboard

**Rationale:** Bulk CSV is the highest-complexity feature and requires a working single-card loop (Phase 2) and async image+email pipeline (Phase 4). Admin dashboard can be built incrementally. This phase also closes remaining auth/audit hardening gaps.
**Delivers:** Bulk creation from form (same amount, N cards), CSV bulk upload endpoint with job ID + async processing, row cap enforcement, per-row status report, issuer dashboard (`index.vue`) with card list/filter/status, cancel + refund flow, per-card audit log
**Addresses features:** CSV bulk upload (variable amounts), bulk creation from form, issuer dashboard, cancel + refund, per-card audit log
**Avoids pitfalls:** Synchronous bulk/CSV (Pitfall 6), auth gaps on admin endpoints (Pitfall 2 final audit), admin dashboard leaking tokens
**Research flag:** CSV bulk upload with async job tracking is moderately complex — consider `/gsd-plan-phase --research-phase 5` for the job-queue/status-endpoint pattern

### Phase 6: Hardening, API Polish, Printable Download

**Rationale:** Final production-readiness sweep: rate limiting on public endpoints, printable PNG/PDF download, API documentation, end-to-end test suite, migration verification on SQLite + PostgreSQL, and the "looks done but isn't" checklist from PITFALLS.md.
**Delivers:** Rate limiting on LNURL-withdraw and redemption endpoints, printable card download endpoint, complete test suite (concurrent redemption load test, 500-row CSV test, cross-wallet access tests), migration idempotency verification
**Avoids pitfalls:** Brute-force of public endpoints (Pitfall 1/2 follow-up), audit trail gaps (Pitfall 5 follow-up)
**Research flag:** Standard patterns for rate limiting in FastAPI/Starlette — no research phase needed

### Phase Ordering Rationale

- **Security-first ordering (Phases 1–3):** All critical security constraints (token hashing, ownership checks, atomic redemption) are resolved before any user-visible feature is built. This prevents the "complete security rewrite" recovery path identified in PITFALLS.md.
- **Dependency chain respected:** Image generation (Phase 4) and bulk CSV (Phase 5) both require a working single-card loop (Phase 2); CSV email delivery requires async image pipeline (Phase 4). The ordering makes each phase independently testable.
- **Redemption URL locked early (Phase 3):** The LNURL-withdraw callback URL structure is the hardest constraint to change post-launch; isolating it in Phase 3 forces it to be explicit and tested before image/email work begins.
- **Bulk complexity deferred (Phase 5):** CSV bulk upload is the highest-complexity feature; building it on top of validated single-card and async delivery primitives reduces implementation risk significantly.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Redemption):** Lightning payment failure/retry handling, hold-invoice vs. immediate-pay trade-offs, and `pay_invoice` timeout/error behavior are nuanced and have limited official documentation. Recommend `--research-phase 3`.
- **Phase 5 (Bulk CSV):** Async job-ID pattern within LNBits (no built-in job queue — must use `create_permanent_task` + DB status table) needs validation against current LNBits task primitives. Recommend `--research-phase 5`.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** LNBits extension structure is fully documented; events extension is a direct code reference.
- **Phase 2 (Core Card API):** Pydantic models, DB migrations, invoice listener — all standard LNBits patterns.
- **Phase 4 (Image + Email):** Pillow compositing and SMTP are well-documented stdlib/core patterns.
- **Phase 6 (Hardening):** FastAPI rate limiting and test patterns are standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Primary sources: live LNBits v1.5.4 `pyproject.toml` + events extension codebase + official docs. Dependency versions directly verified. |
| Features | MEDIUM | Cross-referenced 8+ products and BHN/NAPCO 2025 benchmark (100 programs). Lightning-specific nuances (LNURL-w expiry, walletless flow) are LOW confidence — secondary sources only. |
| Architecture | MEDIUM | Primary source is live events extension codebase (direct reference implementation) + LNBits docs. Specific LNBits v1.5.4 internal API surface not exhaustively verified. |
| Pitfalls | MEDIUM | LNBits-specific pitfalls backed by official docs (HIGH). Security/race-condition pitfalls backed by post-mortems and CertiK guidance (MEDIUM). Some claims are de-facto standards rather than LNBits-specific mandates. |

**Overall confidence:** MEDIUM — sufficient to begin implementation. The security-structural findings (token hashing, atomic redemption, ownership scoping) are HIGH confidence and must not be deferred. Lightning payment edge cases (failure handling, hold invoices) need deeper research before Phase 3 implementation begins.

### Gaps to Address

- **Lightning payment failure handling in redemption (Phase 3):** What happens when `pay_invoice` fails or times out mid-redemption? Card is in `redeeming` state — recovery path not fully documented. Resolve during Phase 3 research.
- **LNBits `create_permanent_task` vs. scheduler for expiry sweeps:** The events extension uses `create_permanent_task`; whether a periodic scheduler primitive exists in LNBits 1.5.4 is unconfirmed. Verify before Phase 3 planning.
- **LNURL-withdraw and LNBits instant wallet interaction:** Research notes that LNBits LNURL-w can create an instant wallet on scan by non-wallet users. Whether this is automatic or requires explicit configuration in the extension needs verification during Phase 3.
- **Pydantic v1 async validators:** LNBits 1.5.x uses Pydantic v1, which has limited async support. Validate that all model usage patterns in `services.py` work correctly with v1 before Phase 2 begins.
- **Template image licensing:** The 2–3 design templates (Christmas, birthday, generic) need either public-domain assets or original designs. Source not specified in research; must be resolved before Phase 4.

---

## Sources

### Primary (HIGH confidence)
- LNBits core `pyproject.toml` v1.5.4 (`/home/exedev/lnbits/pyproject.toml`) — all dependency versions and Python constraint
- LNBits `lnbits/extensions/events` (`/home/exedev/lnbits/lnbits/extensions/events`) — canonical reference implementation for all extension patterns
- LNBits Developer Docs — Building Extensions (`https://docs.lnbits.com/dev/building-extensions`) — extension structure, routers, migrations, dependency policy
- LNBits Developer Docs — Decorators & Auth (`https://docs.lnbits.com/dev/decorators`) — `require_admin_key`, `require_invoice_key`
- LNBits Developer Docs — Background Tasks (`https://docs.lnbits.com/dev/tasks`) — `create_permanent_task`, invoice listeners
- LNBits Core `helpers.py` source — `urlsafe_short_hash()` implementation (`shortuuid.uuid()`)
- LNBits Extension Registry Guidelines (GitHub) — "do not add dependencies" policy and hard rules

### Secondary (MEDIUM confidence)
- BHN/NAPCO 2025 Digital Gift Card Programs Report (100 U.S. programs, 126 criteria) — industry table-stakes baseline
- LNBits GitHub Security Advisory GHSA-qp8j-p87f-c8cc — SSRF via LNURL callback reminder
- CertiK — Building Secure Lightning Network dApps — preimage discipline, atomicity, state-machine rigor
- Lightning TipCards (tipcards.io + GitHub) — LNBits-based gift/tip card reference implementation
- ZBD Vouchers docs — API + email distribution pattern

### Tertiary (LOW confidence — needs validation)
- Azteco, btc-giftcard, UniVoucher, LN Gift, coin-gift — competitor feature analysis
- OopsSec Store / Medium JWT post-mortems — token design security illustrations
- Wrapped Gift Cards fraud prevention guide — brute-force and audit trail patterns

---
*Research completed: 2026-06-29*
*Ready for roadmap: yes*
