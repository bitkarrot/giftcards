# Walking Skeleton — LNBits Gift Cards Extension

**Phase:** 1
**Generated:** 2026-06-29

## Capability Proven End-to-End

An LNBits wallet holder can create a sats-funded gift card, receive a unique shareable redemption link, and a recipient can scan the LNURL QR and redeem the sats via Lightning — the full core loop works before any branding, bulk, or management features are added.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | LNBits extension built as a FastAPI `APIRouter` | Reuses LNBits runtime, wallet, auth, and Lightning primitives; extension is the only supported deployment model per PROJECT.md constraints |
| Data layer | `lnbits.db.Database("ext_giftcards")` with sequential async migrations | SQLite for local development, PostgreSQL for production, all via the core DB abstraction; follows the events extension pattern |
| Auth | `require_admin_key` from `lnbits.decorators` for issuer endpoints; public redemption endpoints unauthenticated | LNBits already provides wallet-scoped API keys; issuer `wallet.id` and `user_id` are derived from the decorator, never from the request body |
| Wallet/funding model | Dedicated card wallet created under issuer user via `lnbits.core.crud.wallets.create_wallet`; fallback to `card_wallet_id=None` if wallet creation fails | Isolates locked sats per card (D-03) while keeping a simple fallback (D-04) that debits the issuer wallet at redemption time |
| Redemption primitive | LNURL-withdraw (LUD-03) via the `lnurl` library already in LNBits core | Recipient wallet pulls sats by providing a BOLT11 invoice; avoids failed pushes to offline wallets and supports walletless guests |
| Token security | `secrets.token_urlsafe(32)` raw token; only SHA-256 hash stored in DB | Unguessable bearer token; a DB leak does not compromise unclaimed cards |
| Background work | `lnbits.tasks.create_permanent_unique_task("ext_giftcards", wait_for_expiry)` + `run_interval(60, _expire_gift_cards)` | Crash-restarting periodic task for expiry sweeps; no external scheduler or queue needed |
| Directory layout | `giftcards/` package in the repo root with standard extension files (`__init__.py`, `models.py`, `crud.py`, `services.py`, `views_api.py`, `views.py`, `tasks.py`, `migrations.py`, `static/js/*.vue`, `tests/`) | Matches the events extension structure and LNBits extension loading conventions |
| Deployment target | Local LNBits dev instance at `/home/exedev/lnbits` via extension symlink or install | The target LNBits v1.5.4 installation is present in the workspace; tests run against it |
| Dependencies | No new runtime Python packages | LNBits policy discourages new dependencies; all required libraries are in the core venv |

## Stack Touched in Phase 1

- [x] Extension scaffold — `__init__.py`, `config.json`, `models.py`, `migrations.py`, `crud.py`, `services.py`, `views_api.py`, `views.py`, `tasks.py`
- [x] Routing — issuer API under `/giftcards/api/v1/cards`, public LNURL endpoints under `/giftcards/api/v1/lnurl`, SPA routes `/giftcards/` and `/giftcards/redeem/{raw_token}`
- [x] Database — real read/write via `giftcards.cards` table; SQLite/PostgreSQL compatible migrations
- [x] UI — interactive Quasar/Vue issuer page and public redemption page wired to the API
- [x] Lightning integration — `update_wallet_balance` for funding, `pay_invoice` for redemption, `create_wallet` for card wallets
- [x] Background processing — expiry sweep task registered with core task helpers
- [x] Local full-stack run — pytest suite against LNBits core; manual browser test of create → redeem flow

## Out of Scope (Deferred to Later Slices)

- Gift card image templates, QR placement, and branding (Phase 2)
- Email, nostr, and printable PNG delivery (Phase 2)
- Bulk CSV creation and same-amount bulk form (Phase 3)
- Authenticated REST API for external systems (Phase 3)
- Issuer dashboard with filters and audit log (Phase 3)
- Rate limiting on public redemption endpoints (Phase 6)
- Cancel + manual refund flow (v2)
- Per-card audit log (v2)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: Branded Delivery — Issuer can choose a design template and deliver the card by email, nostr DM, or printable PNG download.
- Phase 3: Scale & Manage — Issuer can bulk-create cards, use an authenticated REST API, and view/manage cards from a filterable dashboard.
