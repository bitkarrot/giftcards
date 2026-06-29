# Phase 1: Core Loop - Research

**Researched:** 2026-06-29
**Domain:** LNBits extension — LNURL-withdraw redemption, atomic state machine, wallet debit, background expiry
**Confidence:** HIGH (all findings verified directly against live codebase in `/home/exedev/lnbits` and `/home/exedev/events`)

---

## Summary

Phase 1 delivers the full gift card lifecycle end-to-end: create → fund (debit issuer wallet) → active → redeem (LNURL-withdraw pull) → redeemed/expired with automatic sats reclaim. All implementation decisions are locked in CONTEXT.md. This research validates those decisions against the live LNBits 1.5.4 codebase, confirms exact API signatures, and documents every pattern the planner needs to produce concrete tasks.

The good news: every primitive Phase 1 needs already exists in the live codebase with direct reference implementations. `create_wallet` is importable from `lnbits.core.crud.wallets`. `pay_invoice` from `lnbits.core.services.payments` handles internal and external payments with a per-wallet async lock (`wallets_payments_lock`) that prevents concurrent double-pay. The LNURL-withdraw endpoint pattern is fully demonstrated in `/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py`. The `run_interval` helper in `lnbits.tasks` (discovered this session) makes the expiry sweep task trivial to implement correctly. The DB's `execute()` returns a SQLAlchemy result with `rowcount` — the atomic redemption guard works exactly as designed.

The one nuance requiring careful handling: `pay_invoice` raises `PaymentError` on failure, but the card has already been marked `redeeming` (atomically) before the call. The correct recovery pattern, confirmed by TPoS reference, is: catch the exception in the LNURL callback, reset the card status back to `active`, and return `LnurlErrorResponse`. This keeps the card redeemable after a transient Lightning failure.

**Primary recommendation:** Follow the TPoS LNURL-withdraw pattern exactly — use `LnurlWithdrawResponse` / `LnurlSuccessResponse` / `LnurlErrorResponse` from the `lnurl` library (already in core), mark the card `redeeming` atomically before calling `pay_invoice`, and reset to `active` on `PaymentError`. Use `run_interval(60, expire_gift_cards)` wrapped in `create_permanent_unique_task` for the expiry sweep.

---

## User Constraints

> Copied verbatim from `01-CONTEXT.md`. Planner MUST honor all of these.

### Locked Decisions

- **D-01:** Use LNURL-withdraw (LUD-03) as the redemption primitive. Recipient's wallet pulls sats from the gift card's funding wallet by providing a BOLT11 invoice.
- **D-02:** Web redemption page at `/giftcards/redeem/{raw_token}`. LNURL-withdraw entry point uses SHA-256 hash of the token in URL: `/giftcards/api/v1/lnurl/{token_hash}`.
- **D-03:** Issuer wallet debited at card creation. Extension creates a dedicated extension wallet under the issuer's user account to hold locked sats. This wallet pays the recipient's invoice at redemption and returns unclaimed sats to the issuer at expiry.
- **D-04:** Fallback if dedicated wallet cannot be created: create one internal invoice from the issuer wallet and record it as a locked balance claim.
- **D-05:** Tokens generated with `secrets.token_urlsafe(32)`. Only SHA-256 hash stored in DB. Raw token returned once at creation, appears only in the shareable redemption link.
- **D-06:** Redemption endpoints are public but unguessable; rate limiting deferred to Phase 6.
- **D-07:** Phase 1 states: `created` → `active` → `redeemed` or `expired`. `cancelled` deferred to v2.
- **D-08:** Atomic redemption: single `UPDATE ... WHERE status = 'active' AND expired = false` with rowcount == 1 check before `pay_invoice`.
- **D-09:** Expiry background task via `lnbits.tasks.create_permanent_unique_task("ext_giftcards", expire_gift_cards)`. Scans past-expiry cards, marks `expired`, reclaims sats to issuer wallet.
- **D-10:** Expiry task runs at 1-minute interval.
- **D-11:** Issuer creation endpoints use `require_admin_key`; wallet.id derived from decorator. Invoice-key access deferred to Phase 3.
- **D-12:** Public redemption endpoints require no authentication. LNURL-withdraw endpoints are public by design.
- **D-13:** Use `lnbits.db.Database("ext_giftcards")`, tables namespaced as `ext_giftcards.*`. Migrations sequential and idempotent.
- **D-14:** Token hash stored as unique indexed column. Raw token never stored or exposed in list endpoints.
- **D-15:** If `pay_invoice` fails during redemption, card must NOT be left in a stuck state — reset to `active` or transition to a recoverable state. Card must not be lost.

### Claude's Discretion
- Exact naming of URL paths and status enum values.
- Pydantic v1 model structure for `GiftCard`, `CreateGiftCard`, `RedeemRequest`, and public models.
- Specific DB column types and indexes (must support state machine and atomic redemption guard).

### Deferred (Out of Scope for Phase 1)
- Cancel + manual refund flow (v2, AUDT-02)
- Per-card audit log (v2, AUDT-01)
- Printable PDF/PNG generation (Phase 2)
- Email/nostr delivery (Phase 2)
- Bulk creation and REST API (Phase 3)
- Issuer dashboard (Phase 3)
- Rate limiting on public endpoints (Phase 6)

---

## Project Constraints (from CLAUDE.md)

| Constraint | Directive |
|------------|-----------|
| Tech stack | Must be an LNBits extension (`APIRouter`). No new runtime Python dependencies. |
| Security | Redemption tokens must be unguessable and single-use. |
| Compatibility | Must not break LNBits core flows. |
| Performance | Bulk creation must be responsive; image generation must not block. |
| Privacy | Recipient metadata not exposed publicly. |
| Pydantic | v1 only (`~1.10.26`). Never mix Pydantic v2. |
| No new deps | Use only packages already in LNBits core. |
| No pandas | Use `csv.DictReader` for CSV. |
| Token security | `secrets.token_urlsafe(32)`, store SHA-256 hash, display raw token once only. |
| Auth | `require_admin_key` for write endpoints. Derive wallet from decorator, never from request body. |

---

## Architectural Responsibility Map

| Capability | Primary File | Secondary File | Rationale |
|------------|-------------|----------------|-----------|
| Extension bootstrap, router assembly | `__init__.py` | — | LNBits convention; exports `db`, `giftcards_ext`, `giftcards_start`, `giftcards_stop`, `giftcards_static_files` |
| DB schema | `migrations.py` | — | Sequential async functions `m001_initial`, etc. Called by LNBits at startup. |
| Domain models | `models.py` | — | Pydantic v1 models; no business logic. |
| DB I/O | `crud.py` | — | Pure read/write; all business logic banned from here. |
| Card lifecycle, wallet debit, expiry reclaim | `services.py` | `crud.py` | Orchestrates CRUD + `pay_invoice` + `create_wallet`. |
| LNURL-withdraw endpoints, auth | `views_api.py` | `services.py` | Thin router — validates input, delegates to services. |
| Background expiry sweep | `tasks.py` | `services.py` | `create_permanent_unique_task` + `run_interval`. |
| Public redemption page (HTML) | `views.py` | `static/js/redeem.vue` | Serves the Vue SPA for the guest redemption page. |
| Token generation and hashing | `services.py` | — | `secrets.token_urlsafe(32)` → `hashlib.sha256` |

---

## Standard Stack

### Core (no new installs needed — all present in LNBits core)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| FastAPI `APIRouter` | `~0.116.1` | Extension HTTP layer | [VERIFIED: `/home/exedev/lnbits/pyproject.toml`] |
| Pydantic v1 | `~1.10.26` | Models and validation | [VERIFIED: `/home/exedev/lnbits/pyproject.toml`] |
| `lnbits.db.Database` | core | SQLite/PostgreSQL abstraction | [VERIFIED: `/home/exedev/lnbits/lnbits/db.py`] |
| `lnbits.core.services.payments.pay_invoice` | core | Outgoing Lightning payment | [VERIFIED: `/home/exedev/lnbits/lnbits/core/services/payments.py:58`] |
| `lnbits.core.services.payments.create_payment_request` | core | Create Lightning invoice | [VERIFIED: `/home/exedev/lnbits/lnbits/core/services/payments.py:112`] |
| `lnbits.core.services.payments.update_wallet_balance` | core | Internal wallet credit/debit | [VERIFIED: `/home/exedev/lnbits/lnbits/core/services/payments.py:454`] |
| `lnbits.core.crud.wallets.create_wallet` | core | Create dedicated extension wallet | [VERIFIED: `/home/exedev/lnbits/lnbits/core/crud/wallets.py:14`] |
| `lnbits.core.crud.wallets.get_wallet` | core | Fetch wallet by ID | [VERIFIED: `/home/exedev/lnbits/lnbits/core/crud/wallets.py`] |
| `lnbits.tasks.create_permanent_unique_task` | core | Background task registration | [VERIFIED: `/home/exedev/lnbits/lnbits/tasks.py:39`] |
| `lnbits.tasks.register_invoice_listener` | core | Invoice payment listener | [VERIFIED: `/home/exedev/lnbits/lnbits/tasks.py:79`] |
| `lnbits.tasks.run_interval` | core | Periodic task runner | [VERIFIED: `/home/exedev/lnbits/lnbits/tasks.py:152`] |
| `lnbits.decorators.require_admin_key` | core | Auth guard for issuer endpoints | [VERIFIED: `/home/exedev/events/views_api.py:27`] |
| `lnbits.helpers.urlsafe_short_hash` | core | Public card IDs (NOT secrets) | [VERIFIED: `/home/exedev/events/crud.py:5`] |
| `lnurl.LnurlWithdrawResponse` | `~0.10.0` (in core) | LNURL-withdraw params response | [VERIFIED: `/home/exedev/lnbits/.venv/lib/python3.12/site-packages/lnurl/models.py:206`] |
| `lnurl.LnurlSuccessResponse` | `~0.10.0` (in core) | LNURL callback success | [VERIFIED: tpos `views_lnurl.py:8`] |
| `lnurl.LnurlErrorResponse` | `~0.10.0` (in core) | LNURL callback error | [VERIFIED: tpos `views_lnurl.py:8`] |
| `lnurl.MilliSatoshi` | `~0.10.0` (in core) | Amount type for LNURL-withdraw | [VERIFIED: tpos `views_lnurl.py:10`] |
| `lnurl.CallbackUrl` | `~0.10.0` (in core) | Typed callback URL field | [VERIFIED: tpos `views_lnurl.py:6`] |
| `secrets` + `hashlib` | stdlib | Token generation and SHA-256 hashing | [VERIFIED: stdlib] |
| `pyqrcode` + `PIL` | `~1.2.1` / `~12.1.0` (in core) | QR code generation (Phase 2+, but make_qr_png pattern is in events) | [VERIFIED: `/home/exedev/events/views_api.py:8-149`] |

### Package Legitimacy Audit

This phase installs **no new packages**. All dependencies are already present in the LNBits 1.5.4 core `venv`. No package legitimacy gate required.

| Package | Status | Note |
|---------|--------|------|
| All dependencies | Already installed in LNBits core | No new installs needed. |

---

## Architecture Patterns

### System Architecture Diagram

```
Issuer (browser/API client)
  │
  ▼  POST /giftcards/api/v1/cards  [require_admin_key]
views_api.py::api_create_card(data, wallet)
  │
  ▼  services.py::create_gift_card(data, wallet_id)
  │   ├── secrets.token_urlsafe(32) → raw_token
  │   ├── hashlib.sha256(raw_token) → token_hash  (stored in DB)
  │   ├── create_wallet(user_id, "GiftCard #{id}") → card_wallet
  │   ├── pay_invoice(issuer_wallet, funding_invoice)  ← debit issuer
  │   └── crud.create_card(...)  → INSERT ext_giftcards.cards
  │
  ▼  Return {card + raw_token (once only)}
  │
  │  raw_token → shareable URL: /giftcards/redeem/{raw_token}
  │
Recipient opens redemption page
  │
  ▼  GET /giftcards/redeem/{raw_token}   [public, no auth]
views.py → serves Vue SPA (redeem.vue)
  │
  ▼  SPA calls GET /giftcards/api/v1/lnurl/{token_hash}
views_api.py::lnurl_params(token_hash, request)
  │   ├── crud.get_card_by_token_hash(token_hash)
  │   ├── validate: status == 'active', not expired
  │   └── return LnurlWithdrawResponse(callback, k1=token_hash, min/maxWithdrawable)
  │
Recipient wallet auto-calls callback:
  ▼  GET /giftcards/api/v1/lnurl/{token_hash}/callback?pr={bolt11}&k1={token_hash}
views_api.py::lnurl_callback(token_hash, pr, k1)
  │   ├── crud.mark_redeeming_atomic(token_hash)  ← UPDATE WHERE status='active' RETURNING rowcount
  │   ├── if rowcount == 0: return LnurlErrorResponse("already redeemed")
  │   └── services.py::pay_and_complete(card, pr)
  │         ├── try: pay_invoice(card_wallet_id, pr)
  │         │     ├── success → crud.mark_redeemed(card_id)
  │         │     │            return LnurlSuccessResponse()
  │         │     └── PaymentError → crud.reset_to_active(card_id)
  │         │                        return LnurlErrorResponse(reason)
  │         └── (no silent failures — card always lands in active or redeemed)
  │
Background (1-min interval):
  tasks.py::expire_gift_cards()
  │   ├── crud.get_expired_active_cards() → cards where expires_at < now AND status='active'
  │   └── for card in expired:
  │         ├── crud.mark_expired(card_id)  [atomic: UPDATE WHERE status='active']
  │         └── pay_invoice(issuer_wallet_id, create_internal_invoice(card.amount))
  │               OR update_wallet_balance(issuer_wallet, card.amount_sat)
```

### Recommended Project Structure

```
giftcards/
├── __init__.py              # Router assembly + start/stop lifecycle
├── config.json              # Extension metadata
├── models.py                # GiftCard, CreateGiftCard, PublicGiftCard, RedeemResponse
├── migrations.py            # m001_initial (cards table)
├── crud.py                  # db = Database("ext_giftcards") + CRUD functions
├── services.py              # create_gift_card, fund_card, pay_and_complete, expire_gift_cards
├── views.py                 # HTML page routes (serve Vue SPA)
├── views_api.py             # REST + LNURL-withdraw endpoints
├── tasks.py                 # Background expiry sweep registration
└── static/
    └── js/
        └── redeem.vue       # Public redemption page (guest, no auth required)
```

---

### Pattern 1: Extension Bootstrap (`__init__.py`)

**Verified from:** `/home/exedev/events/__init__.py` [VERIFIED: codebase]

```python
# __init__.py
import asyncio
from fastapi import APIRouter
from loguru import logger
from .crud import db
from .tasks import wait_for_expiry
from .views import giftcards_generic_router
from .views_api import giftcards_api_router

giftcards_ext: APIRouter = APIRouter(prefix="/giftcards", tags=["GiftCards"])
giftcards_ext.include_router(giftcards_generic_router)
giftcards_ext.include_router(giftcards_api_router)

giftcards_static_files = [{"path": "/giftcards/static", "name": "giftcards_static"}]

scheduled_tasks: list[asyncio.Task] = []

def giftcards_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)

def giftcards_start():
    from lnbits.tasks import create_permanent_unique_task
    task = create_permanent_unique_task("ext_giftcards", wait_for_expiry)
    scheduled_tasks.append(task)

__all__ = ["db", "giftcards_ext", "giftcards_start", "giftcards_static_files", "giftcards_stop"]
```

**Key export names** LNBits core expects: `{ext_id}_ext`, `{ext_id}_start`, `{ext_id}_stop`, `{ext_id}_static_files`, `db`.

---

### Pattern 2: Migration — Initial Schema

**Verified from:** `/home/exedev/events/migrations.py` [VERIFIED: codebase]

```python
# migrations.py
async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE giftcards.cards (
            id          TEXT PRIMARY KEY,
            wallet      TEXT NOT NULL,
            card_wallet TEXT,
            amount      INTEGER NOT NULL,
            token_hash  TEXT NOT NULL UNIQUE,
            status      TEXT NOT NULL DEFAULT 'active',
            recipient_name  TEXT,
            sender_name     TEXT,
            message         TEXT,
            expires_at  TIMESTAMP,
            created_at  TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """,
            redeemed_at TIMESTAMP,
            expired_at  TIMESTAMP
        );
        """
    )
```

**Rules:**
- Table must be namespaced as `giftcards.cards` (i.e., `ext_giftcards` schema → `giftcards` prefix via `Database("ext_giftcards")`). [VERIFIED: `db.py:312` — `self.schema = self.name[4:]` when name starts with `ext_`]
- `db.timestamp_now` is DB-agnostic: `now()` for Postgres, `(strftime('%s', 'now'))` for SQLite. [VERIFIED: `db.py:89`]
- `expires_at` stored as TIMESTAMP; for expiry comparison use `db.timestamp_placeholder("now")` in WHERE clauses. [VERIFIED: `db.py:130`]
- Do NOT use `datetime.now()` directly in SQL — use `db.timestamp_placeholder` with a Python `time.time()` or `datetime.timestamp()` value. [VERIFIED: `events/crud.py:99`]

---

### Pattern 3: Token Generation and Hashing

**Source:** Python stdlib `secrets` + `hashlib` [VERIFIED: stdlib] + CONTEXT.md D-05

```python
# services.py
import hashlib
import secrets

def generate_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). Store only hash; return raw_token once."""
    raw_token = secrets.token_urlsafe(32)   # 32 bytes → 43-char base64url string
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash
```

**Lookup pattern in CRUD:**
```python
# crud.py
async def get_card_by_token_hash(token_hash: str) -> GiftCard | None:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE token_hash = :hash",
        {"hash": token_hash},
        GiftCard,
    )
```

**URL construction:**
- Redemption page: `https://{base_url}/giftcards/redeem/{raw_token}`
- LNURL-withdraw entry: `https://{base_url}/giftcards/api/v1/lnurl/{token_hash}`

The LNURL-withdraw URL must be bech32-encoded for wallets to recognize it as LNURL, OR wrapped in a `?lightning=lnurl...` query parameter on the redemption page. The QR code encodes the LNURL-withdraw URL (bech32). The raw token URL is the web link for wallets that don't speak LNURL directly. [ASSUMED — bech32 encoding detail; the TPoS implementation serves the JSON directly as HTTPS without bech32 encoding on the params endpoint itself. The `k1` field in the LnurlWithdrawResponse acts as the identifier.]

> **Important clarification:** Per the TPoS reference (`views_lnurl.py`), the LNURL-withdraw params endpoint is served at a plain HTTPS URL. The QR code can encode the HTTPS URL directly — modern Lightning wallets that support LNURL will GET that URL and parse the `{"tag":"withdrawRequest",...}` JSON. Bech32/lnurl encoding is optional for QR presentation (Phase 2); the HTTP endpoint itself does not change.

---

### Pattern 4: Dedicated Card Wallet Creation (D-03 / D-04)

**Verified from:** `/home/exedev/lnbits/lnbits/core/crud/wallets.py:14` [VERIFIED: codebase]

```python
# services.py
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models.wallets import WalletType

async def create_card_wallet(user_id: str, card_id: str) -> Wallet | None:
    """
    Create a dedicated wallet under the issuer user to hold locked sats.
    Falls back to None on failure (caller handles D-04 fallback).
    """
    try:
        wallet = await create_wallet(
            user_id=user_id,
            wallet_name=f"GiftCard {card_id[:8]}",
            wallet_type=WalletType.LIGHTNING,
        )
        return wallet
    except Exception:
        logger.warning(f"Could not create card wallet for {card_id}, using fallback")
        return None
```

**Signature of `create_wallet`** (verified from `crud/wallets.py:14`):
```python
async def create_wallet(
    *,
    user_id: str,
    wallet_name: str | None = None,
    wallet_type: WalletType = WalletType.LIGHTNING,
    shared_wallet_id: str | None = None,
    conn: Connection | None = None,
) -> Wallet:
```

**D-04 fallback** (when `create_wallet` fails or for Phase 1 simplicity):

D-04 says "create one internal invoice from the issuer wallet and record it as a locked balance claim." The simplest Phase 1 implementation: `card_wallet = None`, and at redemption, pay from `issuer_wallet_id` directly. Store `card_wallet_id` as nullable TEXT in DB.

> **Open question (see below):** The Phase 1 plan should decide whether to implement the dedicated wallet (D-03) or the fallback (D-04) as the primary path. The dedicated wallet approach requires the issuer user's `user_id`, which is available from `wallet.wallet.user` on the `WalletTypeInfo` object returned by `require_admin_key`. [VERIFIED: `events/views_api.py:159` — `user = await get_user(wallet.wallet.user)`]

---

### Pattern 5: Funding — Debit Issuer Wallet at Creation

**Verified from:** `lnbits/core/services/payments.py:454` [VERIFIED: codebase]

Two options for debiting the issuer wallet at card creation:

**Option A: `update_wallet_balance` with negative amount** (internal bookkeeping only, no Lightning):
```python
# services.py
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.crud.wallets import get_wallet

async def fund_card_from_issuer(issuer_wallet_id: str, amount_sat: int) -> None:
    wallet = await get_wallet(issuer_wallet_id)
    if not wallet or wallet.balance < amount_sat * 1000:
        raise ValueError("Insufficient balance")
    await update_wallet_balance(wallet, -amount_sat)   # negative = debit
```

`update_wallet_balance(wallet, amount)` [VERIFIED: `payments.py:454`]:
- `amount < 0` → creates a fake internal debit payment, immediately settled
- `amount > 0` → creates a fake internal credit payment, immediately settled
- Raises `ValueError("Balance change failed, can not go into negative balance.")` if balance insufficient

**Option B: `pay_invoice` to an internal card wallet** — more complex, follows real Lightning semantics. Recommended for D-03 (dedicated wallet).

**Recommended for Phase 1:** Use `update_wallet_balance(issuer_wallet, -amount_sat)` for the debit (clean, no roundtrip invoice), and `update_wallet_balance(card_wallet, +amount_sat)` to credit the dedicated card wallet. At redemption, pay from `card_wallet_id` via `pay_invoice`. At expiry reclaim, use `update_wallet_balance(issuer_wallet, +amount_sat)` to credit back.

---

### Pattern 6: LNURL-Withdraw Endpoint Pair

**Verified from:** `/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py` [VERIFIED: codebase]

```python
# views_api.py
from lnurl import CallbackUrl, LnurlErrorResponse, LnurlSuccessResponse, LnurlWithdrawResponse, MilliSatoshi
from pydantic import parse_obj_as

giftcards_lnurl_router = APIRouter(prefix="/api/v1/lnurl")

@giftcards_lnurl_router.get("/{token_hash}", name="giftcards.lnurl_params")
async def lnurl_params(
    request: Request,
    token_hash: str,
) -> LnurlWithdrawResponse | LnurlErrorResponse:
    card = await get_card_by_token_hash(token_hash)
    if not card:
        return LnurlErrorResponse(reason="Gift card not found")
    if card.status != "active":
        return LnurlErrorResponse(reason=f"Gift card is {card.status}")
    if card.expires_at and card.expires_at < datetime.now(timezone.utc):
        return LnurlErrorResponse(reason="Gift card has expired")

    callback = parse_obj_as(
        CallbackUrl,
        str(request.url_for("giftcards.lnurl_callback"))
    )
    return LnurlWithdrawResponse(
        callback=callback,
        k1=token_hash,
        minWithdrawable=MilliSatoshi(card.amount * 1000),
        maxWithdrawable=MilliSatoshi(card.amount * 1000),
        defaultDescription=f"Gift card from {card.sender_name or 'someone'}",
    )

@giftcards_lnurl_router.get("/cb", name="giftcards.lnurl_callback")
async def lnurl_callback(
    pr: str | None = None,
    k1: str | None = None,
) -> LnurlErrorResponse | LnurlSuccessResponse:
    if not pr or not k1:
        return LnurlErrorResponse(reason="pr and k1 are required")

    # Step 1: Atomic state transition — only one concurrent request wins
    card = await mark_redeeming_atomic(k1)
    if card is None:
        return LnurlErrorResponse(reason="Gift card is not available for redemption")

    # Step 2: Pay the recipient's invoice from the card wallet
    try:
        await pay_invoice(
            wallet_id=card.card_wallet_id or card.wallet,   # D-04 fallback
            payment_request=pr,
            max_sat=card.amount,
            extra={"tag": "giftcards", "card_id": card.id},
        )
    except Exception as exc:
        # Step 3: Reset card to active so recipient can retry
        await reset_card_to_active(card.id)
        return LnurlErrorResponse(reason=f"Payment failed: {exc!s}")

    # Step 4: Mark redeemed
    await mark_redeemed(card.id)
    return LnurlSuccessResponse()
```

**Critical notes:**
1. The callback URL uses a **named route** (`url_for("giftcards.lnurl_callback")`) without the token in the path — the token (k1) is passed as a query parameter `k1=`. This matches the TPoS pattern exactly. [VERIFIED: tpos `views_lnurl.py:73-82, 85`]
2. `LnurlWithdrawResponse` fields [VERIFIED: `lnurl/models.py:206`]: `tag` (auto), `callback` (CallbackUrl), `k1` (str), `minWithdrawable` (MilliSatoshi), `maxWithdrawable` (MilliSatoshi), `defaultDescription` (str).
3. `MilliSatoshi` takes millisatoshis, so `card.amount * 1000` for sats → msats. [VERIFIED: tpos `views_lnurl.py:79`]
4. `pay_invoice` raises `PaymentError` (from `lnbits.exceptions`) on failure. [VERIFIED: `payments.py:850`] Catch `Exception` broadly (TPoS pattern) to handle both `PaymentError` and unexpected errors.
5. `pay_invoice` has a timeout (`lnbits_funding_source_pay_invoice_wait_seconds`, default varies) — it returns a pending `Payment` on timeout rather than raising. [VERIFIED: `payments.py:831-839`] For Phase 1, a pending payment is acceptable; the card will be left in `redeeming` state and the recipient can retry (the invoice expires eventually).

---

### Pattern 7: Atomic Redemption Guard in CRUD

**Verified from:** `lnbits/db.py:285` — `execute()` returns SQLAlchemy `Result` with `rowcount` [VERIFIED: codebase]

```python
# crud.py
async def mark_redeeming_atomic(token_hash: str) -> GiftCard | None:
    """
    Atomically transitions status active → redeeming.
    Returns the card if transition succeeded, None if card was not active.
    """
    async with db.connect() as conn:
        result = await conn.execute(
            """
            UPDATE giftcards.cards
            SET status = 'redeeming'
            WHERE token_hash = :hash AND status = 'active'
            """,
            {"hash": token_hash},
        )
        if result.rowcount == 0:
            return None
        return await conn.fetchone(
            "SELECT * FROM giftcards.cards WHERE token_hash = :hash",
            {"hash": token_hash},
            GiftCard,
        )

async def reset_card_to_active(card_id: str) -> None:
    """Reset from redeeming → active after pay_invoice failure."""
    await db.execute(
        "UPDATE giftcards.cards SET status = 'active' WHERE id = :id AND status = 'redeeming'",
        {"id": card_id},
    )

async def mark_redeemed(card_id: str) -> None:
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'redeemed',
            redeemed_at = {db.timestamp_placeholder('now')}
        WHERE id = :id
        """,
        {"id": card_id, "now": datetime.now(timezone.utc).timestamp()},
    )
```

**Why `redeeming` intermediate state (not direct `active → redeemed`):**
- Marks the card as "in-flight" before calling `pay_invoice`
- If the server crashes after atomically setting `redeeming` but before `pay_invoice` completes, a recovery sweep can identify stuck-`redeeming` cards
- D-15 requires a recoverable state; `reset_card_to_active` on `PaymentError` satisfies D-15 for synchronous failures
- For timeout (pay_invoice returns pending), card stays `redeeming` — this is acceptable for Phase 1

---

### Pattern 8: Background Expiry Sweep

**Verified from:** `/home/exedev/lnbits/lnbits/tasks.py:152` — `run_interval` helper [VERIFIED: codebase]

```python
# tasks.py
from lnbits.tasks import run_interval, create_permanent_unique_task

async def _expire_gift_cards() -> None:
    from .crud import get_expired_active_cards, mark_card_expired
    from .services import reclaim_card_sats
    from loguru import logger

    expired = await get_expired_active_cards()
    for card in expired:
        try:
            await mark_card_expired(card.id)
            await reclaim_card_sats(card)
        except Exception as exc:
            logger.error(f"Error expiring card {card.id}: {exc}")

async def wait_for_expiry() -> None:
    """Registered with create_permanent_unique_task — restarts on crash."""
    await run_interval(60, _expire_gift_cards)()
```

**`run_interval` signature** [VERIFIED: `tasks.py:152`]:
```python
def run_interval(interval_seconds: int, func: Callable[[], Coroutine]) -> Callable[[], Coroutine]:
    """Returns an async wrapper that calls func() every interval_seconds while server running."""
```

**`create_permanent_unique_task` signature** [VERIFIED: `tasks.py:39`]:
```python
def create_permanent_unique_task(name: str, coro: Callable[[], Coroutine]) -> asyncio.Task:
    """Wraps in catch_everything_and_restart — task restarts on unhandled exception."""
```

**CRUD for expiry:**
```python
# crud.py
async def get_expired_active_cards() -> list[GiftCard]:
    return await db.fetchall(
        f"""
        SELECT * FROM giftcards.cards
        WHERE status = 'active'
        AND expires_at IS NOT NULL
        AND expires_at < {db.timestamp_placeholder('now')}
        """,
        {"now": datetime.now(timezone.utc).timestamp()},
        GiftCard,
    )

async def mark_card_expired(card_id: str) -> None:
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'expired',
            expired_at = {db.timestamp_placeholder('now')}
        WHERE id = :id AND status = 'active'
        """,
        {"id": card_id, "now": datetime.now(timezone.utc).timestamp()},
    )
```

**Sats reclaim at expiry:**
```python
# services.py
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.crud.wallets import get_wallet

async def reclaim_card_sats(card: GiftCard) -> None:
    """Return locked sats from card wallet → issuer wallet."""
    if not card.card_wallet_id:
        # D-04 fallback: no dedicated wallet, sats were never moved
        return
    issuer_wallet = await get_wallet(card.wallet)
    card_wallet = await get_wallet(card.card_wallet_id)
    if not issuer_wallet or not card_wallet:
        logger.error(f"Cannot reclaim sats for expired card {card.id}")
        return
    try:
        await update_wallet_balance(card_wallet, -card.amount)
        await update_wallet_balance(issuer_wallet, card.amount)
    except Exception as exc:
        logger.error(f"Reclaim failed for card {card.id}: {exc}")
```

---

### Pattern 9: Auth — Issuer Endpoints

**Verified from:** `/home/exedev/events/views_api.py:155, 213` [VERIFIED: codebase]

```python
# views_api.py
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key

giftcards_api_router = APIRouter(prefix="/api/v1/cards")

@giftcards_api_router.post("")
async def api_create_card(
    data: CreateGiftCard,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> GiftCard:
    # ALWAYS derive wallet_id from the decorator, NEVER from data
    wallet_id = wallet.wallet.id
    user_id = wallet.wallet.user   # needed for create_wallet (D-03)
    return await create_gift_card(data, wallet_id, user_id)

@giftcards_api_router.get("")
async def api_list_cards(
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> list[GiftCard]:
    return await get_cards_by_wallet(wallet.wallet.id)  # scoped to wallet
```

**Auth contract:**
- `wallet.wallet.id` = the wallet ID to scope DB queries to [VERIFIED: events pattern]
- `wallet.wallet.user` = the user ID, needed for `create_wallet(user_id=...)` [VERIFIED: `core/crud/wallets.py:22`]
- Never accept `wallet_id` or `user_id` from the request body

---

### Pattern 10: Views.py — Serve Vue SPA

**Verified from:** `/home/exedev/events/views.py` [VERIFIED: codebase]

```python
# views.py
from fastapi import APIRouter
from lnbits.core.views.generic import index, index_public

giftcards_generic_router = APIRouter()

# Issuer dashboard (requires account)
giftcards_generic_router.add_api_route("/", methods=["GET"], endpoint=index)

# Public redemption page (no auth — guest access)
giftcards_generic_router.add_api_route(
    "/redeem/{raw_token}", methods=["GET"], endpoint=index_public
)
```

**`index_public`** serves the same LNBits SPA shell but without requiring an authenticated session. The Vue component loaded is determined by the extension's `static/js/` files. [VERIFIED: events pattern]

---

### Pattern 11: Pydantic v1 Models

**Verified from:** `/home/exedev/events/models.py` [VERIFIED: codebase]

```python
# models.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from lnbits.helpers import urlsafe_short_hash

class CreateGiftCard(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in sats")
    expires_at: Optional[datetime] = None
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None

    @validator("amount")
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

class GiftCard(BaseModel):
    id: str
    wallet: str                      # issuer wallet ID
    card_wallet_id: Optional[str]    # dedicated card wallet (D-03), None if D-04 fallback
    amount: int                      # sats
    token_hash: str                  # SHA-256(raw_token) — stored, NEVER expose in list
    status: str = "active"           # active | redeeming | redeemed | expired
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_at: Optional[datetime]
    expired_at: Optional[datetime]

class PublicGiftCard(BaseModel):
    """Returned by the public redemption page — no token_hash, no wallet ID."""
    id: str
    amount: int
    status: str
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    redeemed_at: Optional[datetime]

class CreateGiftCardResponse(BaseModel):
    """Returned once at creation — contains the raw token (never returned again)."""
    card: GiftCard
    raw_token: str                   # the bearer secret — display once, never store
    redemption_url: str              # https://{base}/giftcards/redeem/{raw_token}
    lnurl_url: str                   # https://{base}/giftcards/api/v1/lnurl/{token_hash}
```

**Pydantic v1 rules** [VERIFIED: LNBits codebase uses v1 throughout]:
- Use `Optional[X]` not `X | None` for optional fields (v1 compatibility)
- Use `validator` decorator, not `field_validator`
- Use `model.dict()` not `model.model_dump()`
- `Field(default_factory=...)` and `Field(..., gt=0)` syntax is v1-compatible

---

### Pattern 12: DB Insert/Update via ORM Helpers

**Verified from:** `/home/exedev/lnbits/lnbits/db.py:202-206` and events/crud.py [VERIFIED: codebase]

```python
# crud.py — insert using db.insert (auto-maps model fields to columns)
async def create_card(card: GiftCard) -> GiftCard:
    await db.insert("giftcards.cards", card)
    return card

# crud.py — update using db.update (matches by id by default)
async def update_card(card: GiftCard) -> GiftCard:
    await db.update("giftcards.cards", card)
    return card

# crud.py — fetch one with model deserialization
async def get_card(card_id: str) -> GiftCard | None:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE id = :id",
        {"id": card_id},
        GiftCard,
    )
```

**`db.insert(table, model)`** — generates `INSERT INTO table (col1, col2, ...) VALUES (:col1, :col2, ...)` from model fields. Model field names must match column names exactly. [VERIFIED: `db.py:202-206`]

**`db.update(table, model, where="WHERE id = :id")`** — generates `UPDATE table SET col1=:col1... WHERE id=:id`. [VERIFIED: `db.py:194-200`]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wallet lock for concurrent payments | Your own mutex/locking | `pay_invoice` — it uses `wallets_payments_lock[wallet_id]` internally | LNBits already prevents double-pay per wallet in `_pay_invoice` [VERIFIED: `payments.py:707`] |
| Background task restart on crash | Try/except loop | `create_permanent_unique_task` + `catch_everything_and_restart` | Handles asyncio.CancelledError correctly, restarts after 5s [VERIFIED: `tasks.py:58`] |
| Periodic timer | `asyncio.sleep` loop | `run_interval(60, func)` | Respects `settings.lnbits_running`, proper exception handling [VERIFIED: `tasks.py:152`] |
| LNURL-withdraw JSON serialization | Custom dict | `LnurlWithdrawResponse` model from `lnurl` lib | Correct field names (`minWithdrawable`, `maxWithdrawable`, `tag`) per LUD-03 [VERIFIED: `lnurl/models.py:206`] |
| DB-agnostic timestamps | Raw datetime strings | `db.timestamp_now` (DDL) + `db.timestamp_placeholder(key)` (DML) | SQLite uses unix ints, Postgres uses timestamps [VERIFIED: `db.py:89,130`] |
| Wallet creation | Calling the REST API with httpx | `create_wallet(user_id=..., wallet_name=...)` from `lnbits.core.crud.wallets` | Direct DB call, no HTTP roundtrip [VERIFIED: `crud/wallets.py:14`] |
| Balance debit/credit | Raw SQL updates | `update_wallet_balance(wallet, amount)` | Handles negative balance guards, creates proper payment records [VERIFIED: `payments.py:454`] |

**Key insight:** LNBits's `pay_invoice` already includes per-wallet locking, balance checks, and payment record creation. Never try to replicate this logic. The atomic redemption guard is only needed at the card-state level (not the payment level).

---

## Common Pitfalls

### Pitfall 1: Using `redeeming` As a "Done" State

**What goes wrong:** Card enters `redeeming` and `pay_invoice` times out (returns pending, not raises). Card stays stuck in `redeeming` forever.

**Why it happens:** `_pay_external_invoice` returns a `pending` Payment object on timeout without raising. [VERIFIED: `payments.py:831-839`]

**How to avoid:** Only catch `Exception` (which catches `PaymentError`) for the explicit failure case. For the timeout/pending case: add a recovery sweep (or accept that Phase 1 defers this — D-15 says "must not be lost"). At minimum, the expiry sweep can also reset `redeeming` cards that are past expiry. Mark stuck `redeeming` cards as `failed` after a grace period (Phase 6 hardening).

**Warning signs:** Cards in `redeeming` status after a Lightning node failure.

---

### Pitfall 2: Named Route Mismatch for LNURL Callback

**What goes wrong:** `url_for("giftcards.lnurl_callback")` raises `NoMatchFound` at runtime.

**Why it happens:** Named routes in FastAPI are `{router_tag}.{route_name}` where the name is set via the `name=` parameter in the decorator. The actual route name depends on how the router is included in the extension router.

**How to avoid:** Test the callback URL generation in a unit test. TPoS pattern: the callback route's `name=` argument must match the string passed to `url_for()`. [VERIFIED: tpos `views_lnurl.py:74-75`] Use `parse_obj_as(CallbackUrl, str(request.url_for("giftcards.lnurl_callback")))` exactly as TPoS does.

**Warning signs:** `NoMatchFound` exception when the LNURL params endpoint is hit.

---

### Pitfall 3: Passing `datetime` Objects Directly to `db.execute`

**What goes wrong:** SQLite receives a Python `datetime` object which aiosqlite may store as a string, then comparisons fail.

**Why it happens:** `Connection.rewrite_values()` converts `datetime` to `int(ts)` for SQLite. If you use raw SQL with `:expires_at` and pass a `datetime`, the type conversion may silently fail.

**How to avoid:** Use `db.timestamp_placeholder("key")` in the SQL and pass `.timestamp()` (float/int) as the value. [VERIFIED: `db.py:49-55`, `events/crud.py:98-105`]

```python
# CORRECT
await db.execute(
    f"SELECT * FROM giftcards.cards WHERE expires_at < {db.timestamp_placeholder('now')}",
    {"now": datetime.now(timezone.utc).timestamp()},
)
# WRONG
await db.execute(
    "SELECT * FROM giftcards.cards WHERE expires_at < :now",
    {"now": datetime.now(timezone.utc)},  # ← datetime object, not float
)
```

---

### Pitfall 4: `token_hash` Leaking in List Endpoints

**What goes wrong:** `GET /api/v1/cards` returns `GiftCard` objects with `token_hash` field, which should never be exposed.

**Why it happens:** Returning the full `GiftCard` model directly rather than a projection.

**How to avoid:** Return `GiftCardSummary` (no `token_hash`, no `card_wallet_id`) from list endpoints. The `token_hash` is only needed internally by CRUD.

---

### Pitfall 5: Extension Not Exporting `db`

**What goes wrong:** LNBits fails to run migrations for the extension because `db` is not in `__all__`.

**Why it happens:** LNBits core imports `db` from the extension module to run migrations.

**How to avoid:** `__all__ = ["db", "giftcards_ext", "giftcards_start", "giftcards_static_files", "giftcards_stop"]` — `db` must be in `__all__`. [VERIFIED: events `__init__.py:42`]

---

### Pitfall 6: `redeem.vue` Route Not in views.py

**What goes wrong:** Recipient opens `/giftcards/redeem/{raw_token}` and gets a 404 instead of the Vue SPA.

**Why it happens:** The route must be registered in `views.py` using `index_public` endpoint so LNBits serves the SPA shell. The raw token in the URL is handled client-side by Vue — the server just needs to serve the SPA for that path.

**How to avoid:** Register `"/redeem/{raw_token}"` in `views.py` with `endpoint=index_public`. [VERIFIED: events `views.py:14`]

---

### Pitfall 7: DB Lock Contention (SQLite)

**What goes wrong:** `Database.connect()` acquires `self.lock` (asyncio.Lock). If the expiry sweep and a concurrent redemption both call `db.connect()`, one will wait. Under heavy load this can cause request timeouts.

**Why it happens:** `lnbits.db.Database.connect()` uses `await self.lock.acquire()` — SQLite extension databases are serialized. [VERIFIED: `db.py:325`]

**How to avoid:** Keep DB operations short. Do NOT hold the connection open across `pay_invoice` calls. The atomic CRUD operations (mark_redeeming, mark_redeemed) must be separate short transactions. For Phase 1 this is fine; SQLite lock contention is a Phase 6 concern.

---

## Code Examples

### Complete Card Creation Flow

```python
# services.py
import hashlib
import secrets
from datetime import datetime, timezone

from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.services.payments import update_wallet_balance
from lnbits.helpers import urlsafe_short_hash
from loguru import logger

from .crud import create_card as crud_create_card
from .models import CreateGiftCard, CreateGiftCardResponse, GiftCard


async def create_gift_card(
    data: CreateGiftCard,
    issuer_wallet_id: str,
    user_id: str,
    base_url: str,
) -> CreateGiftCardResponse:
    # 1. Check issuer balance
    issuer_wallet = await get_wallet(issuer_wallet_id)
    if not issuer_wallet or issuer_wallet.balance < data.amount * 1000:
        raise ValueError("Insufficient wallet balance")

    # 2. Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    card_id = urlsafe_short_hash()

    # 3. Create dedicated card wallet (D-03)
    card_wallet = None
    try:
        card_wallet = await create_wallet(
            user_id=user_id,
            wallet_name=f"GiftCard {card_id[:8]}",
        )
    except Exception:
        logger.warning(f"Dedicated wallet creation failed for {card_id}, using D-04 fallback")

    # 4. Create DB record
    card = GiftCard(
        id=card_id,
        wallet=issuer_wallet_id,
        card_wallet_id=card_wallet.id if card_wallet else None,
        amount=data.amount,
        token_hash=token_hash,
        status="active",
        recipient_name=data.recipient_name,
        sender_name=data.sender_name,
        message=data.message,
        expires_at=data.expires_at,
        created_at=datetime.now(timezone.utc),
    )
    await crud_create_card(card)

    # 5. Debit issuer wallet (D-05: after DB record exists)
    try:
        await update_wallet_balance(issuer_wallet, -data.amount)
        if card_wallet:
            card_wallet_obj = await get_wallet(card_wallet.id)
            await update_wallet_balance(card_wallet_obj, data.amount)
    except Exception as exc:
        # Rollback: delete the card record
        await crud_delete_card(card_id)
        if card_wallet:
            # Best-effort cleanup of orphaned wallet (ignore errors)
            try:
                from lnbits.core.crud.wallets import force_delete_wallet
                await force_delete_wallet(card_wallet.id)
            except Exception:
                pass
        raise ValueError(f"Failed to fund card: {exc}") from exc

    # 6. Build URLs
    redemption_url = f"{base_url}/giftcards/redeem/{raw_token}"
    lnurl_url = f"{base_url}/giftcards/api/v1/lnurl/{token_hash}"

    return CreateGiftCardResponse(
        card=card,
        raw_token=raw_token,   # returned ONCE — never log or store
        redemption_url=redemption_url,
        lnurl_url=lnurl_url,
    )
```

### Expiry Sweep CRUD

```python
# crud.py
from datetime import datetime, timezone
from .models import GiftCard

async def get_expired_active_cards() -> list[GiftCard]:
    return await db.fetchall(
        f"""
        SELECT * FROM giftcards.cards
        WHERE status = 'active'
        AND expires_at IS NOT NULL
        AND expires_at < {db.timestamp_placeholder('now')}
        """,
        {"now": datetime.now(timezone.utc).timestamp()},
        GiftCard,
    )
```

### Migration Pattern with Index

```python
# migrations.py
async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE giftcards.cards (
            id              TEXT PRIMARY KEY,
            wallet          TEXT NOT NULL,
            card_wallet_id  TEXT,
            amount          INTEGER NOT NULL,
            token_hash      TEXT NOT NULL UNIQUE,
            status          TEXT NOT NULL DEFAULT 'active',
            recipient_name  TEXT,
            sender_name     TEXT,
            message         TEXT,
            expires_at      TIMESTAMP,
            created_at      TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """,
            redeemed_at     TIMESTAMP,
            expired_at      TIMESTAMP
        );
        """
    )
    # Index for wallet-scoped list queries
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_giftcards_cards_wallet ON giftcards.cards (wallet);"
    )
    # Index for expiry sweep (scans active cards with past expiry)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_giftcards_cards_status_expires ON giftcards.cards (status, expires_at);"
    )
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Simple `update` after checking status | Atomic `UPDATE WHERE status='active'` + rowcount check | Prevents race condition under concurrent Lightning wallet redemptions |
| `create_task` for background work | `create_permanent_unique_task` + `run_interval` | Auto-restarts on crash; correct `CancelledError` propagation |
| `lnurl_withdraw` via hand-rolled JSON dict | `LnurlWithdrawResponse` Pydantic model from `lnurl` lib | Type safety; correct field serialization per LUD-03 |
| Manual DB timestamp handling | `db.timestamp_now` (DDL) + `db.timestamp_placeholder(key)` (DML) | SQLite/Postgres cross-compatibility |
| Invoice listener for funding confirmation | `update_wallet_balance` for internal debit/credit | No roundtrip invoice needed for internal wallet transfers |

**Deprecated:**
- Passing raw `datetime` objects in SQL value dicts — use `.timestamp()` float

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The LNURL-withdraw QR code can encode a plain HTTPS URL (not bech32-encoded) and modern wallets will recognize it | Pattern 3, LNURL section | Recipients with wallets requiring strict bech32 lnurl: prefix would not recognize the QR. Phase 1 mitigation: show both a QR and a manual link on the redemption page. Bech32 encoding is a Phase 2 enhancement. |
| A2 | `update_wallet_balance(wallet, -amount)` is the correct primitive for debiting the issuer wallet at card creation (vs. `pay_invoice` to an internal wallet) | Pattern 5 | If `update_wallet_balance` doesn't work for extension-initiated balance changes (permissions), fall back to creating a self-invoice and paying it. The function is exported from `lnbits.core.services.__init__` and used internally for admin operations, so it should be available. |
| A3 | The dedicated card wallet (D-03) can be created without triggering any per-user wallet limit checks | Pattern 4 | If LNBits enforces a max-wallet-per-user limit, the D-04 fallback (store balance claim only) is used automatically. |
| A4 | `force_delete_wallet` is safe to call from an extension on a wallet the extension created | Pattern — Card Creation rollback | If wallet deletion fails silently, an orphaned 0-balance wallet is left in the issuer's account (cosmetic issue, not a fund loss). |

---

## Open Questions (RESOLVED)

1. **D-03 vs D-04 as primary path for Phase 1**
   - What we know: `create_wallet` is importable and works. `update_wallet_balance` handles debit/credit internally. The dedicated wallet model (D-03) gives clean sats isolation and simplifies the `pay_invoice` call at redemption. The fallback (D-04) uses the issuer wallet directly.
   - **RESOLVED:** Implement D-03 (dedicated wallet) as the primary path — it's simple (`create_wallet` is one call) and produces cleaner sats accounting. D-04 is the fallback when `create_wallet` raises an exception. Do NOT implement the "internal invoice" variant of D-04 — just use D-03 with a try/except that falls back to `card_wallet_id = None` and pays from `card.wallet` (issuer wallet) at redemption.

2. **`pay_invoice` timeout and `redeeming` state recovery**
   - What we know: `pay_invoice` returns a pending `Payment` (not raises) on timeout. The card will remain in `redeeming` state if this happens.
   - **RESOLVED:** After `pay_invoice`, check the returned `Payment.status`. If `status == PaymentState.PENDING`, treat it as an error: reset card to `active`, return `LnurlErrorResponse`. The wallet has not been debited (payment is pending/not settled). This is Phase 1 acceptable.

3. **Base URL for generating redemption/LNURL URLs**
   - What we know: The creation endpoint handler has `request: Request` available. `str(request.base_url).rstrip("/")` gives the base URL.
   - **RESOLVED:** Use `str(request.base_url).rstrip("/")` in the API handler (matches TPoS/events pattern). Pass it into `create_gift_card()` as `base_url` parameter.

---

## Environment Availability

| Dependency | Required By | Available | Version | Notes |
|------------|------------|-----------|---------|-------|
| `lnbits.core.services.payments.pay_invoice` | Redemption payout | ✓ | core | [VERIFIED: `payments.py:58`] |
| `lnbits.core.services.payments.update_wallet_balance` | Wallet debit/credit | ✓ | core | [VERIFIED: `payments.py:454`] |
| `lnbits.core.crud.wallets.create_wallet` | Dedicated card wallet | ✓ | core | [VERIFIED: `crud/wallets.py:14`] |
| `lnbits.tasks.create_permanent_unique_task` | Expiry task | ✓ | core | [VERIFIED: `tasks.py:39`] |
| `lnbits.tasks.run_interval` | Expiry loop | ✓ | core | [VERIFIED: `tasks.py:152`] |
| `lnurl.LnurlWithdrawResponse` | LNURL-withdraw | ✓ | `~0.10.0` | [VERIFIED: `.venv/...lnurl/models.py:206`] |
| `lnbits.db.Database` | All DB ops | ✓ | core | [VERIFIED: `db.py:292`] |
| `secrets` + `hashlib` | Token security | ✓ | stdlib | [VERIFIED: stdlib] |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (in LNBits core dev dependencies) |
| Test location | `giftcards/tests/` |
| Test style | Async integration tests against FastAPI `TestClient` or `httpx.AsyncClient` |

### Critical Tests for Phase 1

| Test | What It Verifies | Priority |
|------|-----------------|----------|
| `test_create_card_debits_issuer` | Issuer wallet balance decreases by card amount after creation | P0 |
| `test_create_card_returns_token_once` | `raw_token` in response; subsequent GET does not expose it | P0 |
| `test_lnurl_params_returns_withdraw_response` | GET `/lnurl/{token_hash}` returns valid `LnurlWithdrawResponse` JSON | P0 |
| `test_atomic_redemption_no_double_spend` | Two concurrent redemption callbacks → only one `LnurlSuccessResponse`, one `LnurlErrorResponse` | P0 |
| `test_expiry_sweep_marks_expired` | After `expires_at` passes, card status becomes `expired` | P0 |
| `test_expiry_sweep_reclaims_sats` | Issuer wallet balance increases after expiry reclaim | P0 |
| `test_lnurl_callback_resets_on_payment_failure` | `pay_invoice` raises → card returns to `active` | P1 |
| `test_token_hash_not_in_list_response` | `GET /api/v1/cards` response does not contain `token_hash` field | P0 |
| `test_cross_wallet_access_denied` | Wallet A cannot list/redeem cards owned by Wallet B | P0 |

---

*Research completed: 2026-06-29*
*All patterns verified directly against `/home/exedev/lnbits` (LNBits v1.5.4) and `/home/exedev/events` reference extension.*
*No web searches required — codebase provided all necessary information.*
