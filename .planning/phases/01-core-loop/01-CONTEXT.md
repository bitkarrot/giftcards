# Phase 1: Core Loop - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the end-to-end gift card lifecycle: an issuer creates a sats-denominated gift card with a fixed amount, expiration date, and recipient metadata; the card is funded by debiting the issuer wallet; the recipient receives a unique redemption link and can redeem the sats via Lightning. No branding, delivery, bulk, or dashboard features are in this phase — only the secure core loop.

</domain>

<decisions>
## Implementation Decisions

### Redemption mechanism
- **D-01:** Use LNURL-withdraw (LUD-03) as the redemption primitive. The recipient's wallet pulls sats from the gift card's funding wallet by providing a BOLT11 invoice. This avoids failed pushes to offline wallets, supports guest/walletless recipients, and is the Lightning-native pattern used by LNBits withdraw extension and TipCards.
- **D-02:** The web redemption page (`/giftcards/redeem/{raw_token}`) displays card details and a QR code / link that triggers the LNURL-withdraw flow. The LNURL-withdraw entry point uses the SHA-256 hash of the token, not the raw token, in the URL (`/giftcards/api/v1/lnurl/{token_hash}`).

### Funding and wallet model
- **D-03:** The issuer wallet is debited at card creation. The extension creates and uses a dedicated extension wallet under the issuer's user account to hold the locked sats. This wallet pays the recipient's invoice at redemption and returns unclaimed sats to the issuer at expiry.
- **D-04:** If a dedicated extension wallet cannot be created for the issuer, fall back to creating one internal invoice from the issuer wallet and recording it as a locked balance claim (sufficient for Phase 1, with a follow-up to harden to real wallet isolation).

### Token security
- **D-05:** Raw redemption tokens are generated with `secrets.token_urlsafe(32)`. Only the SHA-256 hash of the token is stored in the database. The raw token is returned exactly once at creation and appears only in the shareable redemption link.
- **D-06:** Redemption endpoints are public but unguessable; rate limiting is deferred to Phase 6.

### Card state machine
- **D-07:** Phase 1 supports states: `created` → `active` → `redeemed` or `expired`. The `cancelled` state is deferred to v2 (AUDT-02). A card becomes `active` immediately after creation and successful funding.
- **D-08:** Redemption is atomic: a single `UPDATE ... WHERE status = 'active' AND expired = false` checks rowcount == 1 before `pay_invoice` is invoked. Concurrent redemption attempts cannot double-spend.

### Expiry and reclaim
- **D-09:** Expiry is enforced by a periodic background task registered via `lnbits.tasks.create_permanent_unique_task("ext_giftcards", expire_gift_cards)`. The task scans for cards past their expiration date, marks them `expired`, and reclaims remaining sats to the issuer wallet.
- **D-10:** The expiry task runs at a 1-minute interval. This is acceptable for Phase 1; tighter scheduling is deferred to Phase 6.

### API and auth
- **D-11:** Issuer creation endpoints use `require_admin_key` and derive `wallet.id` from the decorator. Issuer list endpoints also use `require_admin_key` in Phase 1; invoice-key access is deferred to Phase 3.
- **D-12:** Public redemption endpoints require no authentication. LNURL-withdraw endpoints are public by design.

### Database
- **D-13:** Use `lnbits.db.Database("ext_giftcards")` and namespace tables as `ext_giftcards.*`. Migrations are sequential and idempotent across SQLite and PostgreSQL, following the events extension pattern.
- **D-14:** Store the token hash as a unique indexed column. Do not store the raw token or expose it in list endpoints.

### Error handling
- **D-15:** If `pay_invoice` fails during redemption, transition the card to a `redeeming_failed` (or keep as `active` if safe) and log the error. Do not leave the card stuck in `redeeming` without a retry path. The exact failure recovery state is left to the planner's discretion within the constraint that the card must not be lost.

### Claude's Discretion
- Exact naming of URL paths and status enum values, provided they follow the decisions above.
- Pydantic v1 model structure for `GiftCard`, `CreateGiftCard`, `RedeemRequest`, and public models.
- Specific DB column types and indexes, as long as the schema supports the state machine and atomic redemption guard.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project requirements and research
- `.planning/PROJECT.md` — Project scope, core value, constraints, and key decisions.
- `.planning/REQUIREMENTS.md` — v1 requirements mapped to phases; Phase 1 covers GCARD-01 through GCARD-05 and REDM-01 through REDM-05.
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and dependencies.
- `.planning/research/SUMMARY.md` — Research conclusions: stack, architecture, pitfalls, and phase ordering rationale.
- `.planning/research/ARCHITECTURE.md` — LNBits extension anatomy and component boundaries.
- `.planning/research/PITFALLS.md` — Critical security and operational pitfalls.

### Reference codebase
- `/home/exedev/events/__init__.py` — Extension bootstrap and scheduled task registration.
- `/home/exedev/events/models.py` — Pydantic v1 models and validators.
- `/home/exedev/events/migrations.py` — Sequential, idempotent migration pattern.
- `/home/exedev/events/crud.py` — Pure DB I/O using `lnbits.db.Database`.
- `/home/exedev/events/services.py` — Business logic, email notification patterns, background task helpers.
- `/home/exedev/events/views_api.py` — FastAPI routers, auth decorators (`require_admin_key`, `require_invoice_key`), QR generation with `pyqrcode` and `PIL`.
- `/home/exedev/events/tasks.py` — Invoice listener registration with `register_invoice_listener`.
- `/home/exedev/lnbits/lnbits/core/services/payments.py` — `pay_invoice` and `create_payment_request` primitives.

### LNBits documentation
- LNBits extension development docs at https://docs.lnbits.com/ (referenced by research; use official docs for current API details).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- `lnbits.db.Database` abstraction — reuse for SQLite/PostgreSQL compatibility.
- `lnbits.decorators.require_admin_key` / `require_invoice_key` — reuse for auth.
- `lnbits.core.services.payments.pay_invoice` — reuse for redemption payouts.
- `lnbits.core.services.payments.create_payment_request` — reuse for funding invoices if needed.
- `lnbits.tasks.create_permanent_unique_task` — reuse for the expiry sweep task.
- `lnbits.helpers.urlsafe_short_hash` — reuse for public card IDs, NOT for redemption secrets.
- `pyqrcode` + `PIL` patterns in `/home/exedev/events/views_api.py` — reuse for QR generation in later phases; Phase 1 only needs the redemption URL/QR if tests require it.

### Established patterns
- Extensions register routers in `__init__.py` with `APIRouter(prefix="/giftcards", tags=["GiftCards"])`.
- Migrations in `migrations.py` are async functions `mNNN_name(db)` that call `db.execute()`.
- CRUD in `crud.py` is pure I/O; business logic lives in `services.py`.
- Models in `models.py` use Pydantic v1 (`BaseModel`, `validator`) for request/response and DB serialization.
- Static files are declared in `__init__.py` as `giftcards_static_files = [{"path": "/giftcards/static", "name": "giftcards_static"}]`.

### Integration points
- Extension routers are mounted by LNBits core at startup.
- Auth keys are extracted from `X-Api-Key` header by LNBits decorators.
- Background tasks are started in `giftcards_start()` and cancelled in `giftcards_stop()`.
- Public redemption endpoints are mounted under the same router but have no `Depends` auth.

</code_context>

<specifics>
## Specific Ideas

- Redemption page should be mobile-first and work without a LNBits account (guest redemption).
- The LNURL-withdraw QR code should encode `https://{lnbits_baseurl}/giftcards/api/v1/lnurl/{token_hash}`.
- The shareable web link should encode `https://{lnbits_baseurl}/giftcards/redeem/{raw_token}`.
- Expired cards should show a clear "expired" message and, if possible, an automatic reclaim notice to the issuer.

</specifics>

<deferred>
## Deferred Ideas

- Cancel + manual refund flow — belongs to v2 (AUDT-02).
- Per-card audit log — belongs to v2 (AUDT-01).
- Printable PDF/PNG generation — belongs to Phase 2.
- Email/nostr delivery — belongs to Phase 2.
- Bulk creation and REST API — belongs to Phase 3.
- Issuer dashboard — belongs to Phase 3.
- Design templates and QR placement — belongs to Phase 2.
- Rate limiting on public endpoints — belongs to Phase 6.

</deferred>

---

*Phase: 1-Core Loop*
*Context gathered: 2026-06-29*
