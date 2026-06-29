# Architecture Research

**Domain:** LNBits Extension — Gift Card Lifecycle (create, fund, distribute, redeem)
**Researched:** 2026-06-29
**Confidence:** MEDIUM — primary source is live codebase (events extension) cross-checked with LNBits docs

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      Browser / Client                            │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  Admin/Issuer│  │ Recipient Page │  │  Redemption Page     │  │
│  │  Vue SPA     │  │ (public, guest)│  │  (guest, no auth)    │  │
│  └──────┬───────┘  └───────┬────────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼─────────────────────┼──────────────┘
          │  REST + WS       │  REST (public)       │  REST (public)
┌─────────▼──────────────────▼─────────────────────▼──────────────┐
│                    FastAPI Extension Layer                        │
│                                                                  │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  views_api.py    │  │  views_api.py  │  │  views_api.py    │  │
│  │  /api/v1/cards   │  │  /api/v1/redeem│  │  /api/v1/qr      │  │
│  │  (admin_key)     │  │  (no auth)     │  │  (no auth)       │  │
│  └────────┬─────────┘  └───────┬────────┘  └────────┬─────────┘  │
│           │                    │                     │            │
│  ┌────────▼────────────────────▼─────────────────────▼─────────┐  │
│  │                     services.py                              │  │
│  │  card_lifecycle │ redemption_logic │ image_gen │ email/nostr │  │
│  └────────┬────────────────────────────────────────────────────┘  │
│           │                                                       │
│  ┌────────▼───────────────────────────────────────────────────┐   │
│  │                      crud.py                               │   │
│  │  create_card │ get_card │ update_card │ redeem_card_atomic │   │
│  └────────┬───────────────────────────────────────────────────┘   │
│           │                                                       │
│  ┌────────▼───────────────────────────────────────────────────┐   │
│  │                     tasks.py                               │   │
│  │  wait_for_paid_invoices │ payment_listeners (WS queues)    │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────────┐
│                    LNBits Core Services                          │
│  create_payment_request │ pay_invoice │ execute_withdraw         │
│  register_invoice_listener │ lnurl library                      │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────────┐
│              SQLite / PostgreSQL / CockroachDB                   │
│  ext_giftcards.cards  │  ext_giftcards.batches                  │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `__init__.py` | Extension bootstrap: register routers, static files, start/stop hooks | `APIRouter(prefix="/giftcards")`, export `db`, `giftcards_ext`, `giftcards_start`, `giftcards_stop`, `giftcards_static_files` |
| `config.json` | Extension metadata consumed by LNBits extension manager | `id`, `version`, `name`, `min_lnbits_version`, `short_description`, `tile` image path |
| `models.py` | Pydantic domain models: Create\*, internal, public projections | `GiftCard`, `CreateGiftCard`, `PublicGiftCard`, `RedeemRequest`, `Batch` |
| `migrations.py` | Sequential DB schema versioning (`m001_initial`, `m002_*`) | Async functions called by LNBits on startup; add columns via `ALTER TABLE` in new migrations |
| `crud.py` | Pure database I/O; no business logic | `db = Database("ext_giftcards")`, `create_card()`, `get_card()`, `mark_redeemed_atomic()` |
| `services.py` | Business logic, orchestration, external calls | Card lifecycle transitions, image generation, email/nostr delivery, LNURL-withdraw creation |
| `views.py` | HTML page routes (serve the Vue SPA) | `add_api_route("/", index)`, `add_api_route("/redeem/{token}", index_public)` |
| `views_api.py` | REST + WebSocket API endpoints; auth enforcement | One `APIRouter` per resource group; `Depends(require_admin_key)` for issuer ops, no-auth for public redemption |
| `tasks.py` | Background payment listener; WebSocket push | `register_invoice_listener(queue, "ext_giftcards")`, per-payment-hash WS queues |
| `static/js/` | Vue SPA components (Quasar UI, no build step needed) | `index.vue` (admin), `redeem.vue` (public guest page) |
| `static/image/` | Template images for gift card designs | `.jpg` / `.png` backgrounds that get QR overlaid at render time |

---

## Recommended Project Structure

```
giftcards/
├── __init__.py              # Router assembly, export symbols, start/stop
├── config.json              # Extension metadata
├── manifest.json            # Release manifest (for extension registry)
├── models.py                # GiftCard, Batch, CreateGiftCard, RedeemRequest, etc.
├── migrations.py            # m001_initial, m002_*, ... (append-only)
├── crud.py                  # db = Database("ext_giftcards") + CRUD functions
├── services.py              # Business logic: lifecycle, image gen, delivery
├── views.py                 # HTML page routes (serve SPA)
├── views_api.py             # REST API + WebSocket endpoints
├── tasks.py                 # Invoice listener, WS payment push
├── static/
│   ├── image/
│   │   ├── giftcard.png         # Default template background
│   │   ├── christmas.jpg        # Seasonal template
│   │   └── birthday.jpg         # Seasonal template
│   └── js/
│       ├── index.vue            # Admin/issuer dashboard SPA
│       └── redeem.vue           # Public redemption page
└── tests/
    ├── __init__.py
    └── test_init.py             # Integration tests
```

### Structure Rationale

- **`crud.py` stays pure I/O:** Business rules live in `services.py`, not in CRUD. CRUD functions only read/write DB. This mirrors the events, tpos, and satspay extensions exactly.
- **`services.py` owns lifecycle state transitions:** `fund_card()`, `mark_redeemed()`, `expire_card()` live here; they coordinate CRUD + LNBits core services + delivery.
- **`views_api.py` handles auth and input validation only:** Delegates to services for logic. Keeps router functions thin.
- **`tasks.py` owns async plumbing:** Invoice listener + per-hash WebSocket queues. Matches events extension pattern exactly.
- **`static/js/` is Vue SFCs without build step:** LNBits extensions serve `.vue` files directly — no webpack/vite required for the extension itself (LNBits serves them via its asset pipeline).

---

## Architectural Patterns

### Pattern 1: LNURL-Withdraw as Redemption Mechanism

**What:** Gift card redemption is implemented as an LNURL-withdraw endpoint. The card's unique token is the `k1` nonce. When the recipient's Lightning wallet calls the withdraw callback, the extension pays the wallet via `pay_invoice()` from the issuer's wallet.

**When to use:** Whenever sats need to flow from issuer wallet → recipient arbitrary wallet without requiring the recipient to have an LNBits account.

**Trade-offs:** Recipient needs an LNURL-capable Lightning wallet. No LNBits account required. Delivery is pull-based (recipient initiates), which prevents failed pushes to offline wallets.

**Example:**
```python
# views_api.py — LNURL-withdraw callback
@giftcards_api_router.get("/api/v1/lnurlw/{token}")
async def lnurlw_params(token: str, request: Request):
    """Step 1: wallet fetches withdrawal parameters"""
    card = await get_card_by_token(token)
    if not card or card.redeemed or card.expired:
        return {"status": "ERROR", "reason": "Invalid or already redeemed"}
    return {
        "tag": "withdrawRequest",
        "callback": str(request.url_for("lnurlw_callback", token=token)),
        "k1": token,
        "minWithdrawable": card.amount_msat,
        "maxWithdrawable": card.amount_msat,
        "defaultDescription": f"Gift card: {card.memo}",
    }

@giftcards_api_router.get("/api/v1/lnurlw/{token}/callback")
async def lnurlw_callback(token: str, pr: str, k1: str):
    """Step 2: wallet sends a payment request; we pay it"""
    card = await redeem_card_atomic(token)  # atomic: marks redeemed or raises
    if not card:
        return {"status": "ERROR", "reason": "Card already redeemed"}
    await pay_invoice(wallet_id=card.wallet, payment_request=pr,
                      extra={"tag": "giftcards", "card_id": card.id})
    return {"status": "OK"}
```

### Pattern 2: Invoice Listener for Funding Confirmation

**What:** When a gift card requires upfront funding (issuer pays a Lightning invoice to pre-load the card), the extension tags the invoice with `{"tag": "giftcards"}` at creation. `tasks.py` listens on the global invoice queue and transitions the card from `PENDING` → `FUNDED` when payment is confirmed.

**When to use:** Pre-funded card model where the issuer transfers sats into the card at creation time.

**Trade-offs:** Requires issuer to have sats in their LNBits wallet at card creation. Alternative: deduct at redemption time (simpler, but requires the wallet to have balance when redeemed).

**Example:**
```python
# tasks.py
async def wait_for_paid_invoices():
    invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_giftcards")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)

async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "giftcards":
        return
    card = await get_card(payment.extra.get("card_id"))
    if not card:
        return
    await mark_card_funded(card)
    # push to any waiting WebSocket clients
    for queue in payment_listeners.get(payment.payment_hash, []):
        queue.put_nowait(card)
```

### Pattern 3: Atomic Redemption Guard

**What:** Use a DB-level atomic update to prevent double-redemption race conditions. The CRUD function attempts to transition `redeemed = false → true` in a single UPDATE with WHERE clause; returns `None` if the card was already redeemed.

**When to use:** Any state transition that must happen exactly once under concurrent requests.

**Trade-offs:** Requires DB-level atomicity (works with SQLite WAL mode and PostgreSQL). Do not rely on application-level read-check-write sequences.

**Example:**
```python
# crud.py
async def redeem_card_atomic(token: str) -> GiftCard | None:
    """Returns the card if redemption was granted, None if already redeemed."""
    async with db.connect() as conn:
        result = await conn.execute(
            """
            UPDATE giftcards.cards
            SET redeemed = true, redeemed_at = :now
            WHERE token = :token AND redeemed = false AND expired = false
            """,
            {"token": token, "now": datetime.now(timezone.utc).timestamp()},
        )
        if result.rowcount == 0:
            return None
        return await get_card_by_token(token, conn=conn)
```

### Pattern 4: Image Generation via PIL Compositing + asyncio.to_thread

**What:** Gift card image = template background JPEG/PNG + QR code pasted at a template-defined position. Image generation is CPU-bound and must run off the async event loop.

**When to use:** Any image rendering endpoint (`/api/v1/qr/{card_id}`). Also for bulk batch image generation.

**Trade-offs:** `asyncio.to_thread()` adds minor overhead but prevents stalling the server. For bulk (100+ cards), use `asyncio.gather()` with thread pool to parallelize.

**Example:**
```python
# services.py
from PIL import Image
from io import BytesIO
import asyncio

def _render_card_image_sync(template_bytes: bytes, qr_data: str,
                             qr_x: int, qr_y: int, qr_size: int) -> bytes:
    qr_img = make_qr_png(qr_data, size=qr_size)
    template = Image.open(BytesIO(template_bytes)).convert("RGBA")
    template.paste(qr_img, (qr_x, qr_y))
    output = BytesIO()
    template.save(output, format="PNG")
    return output.getvalue()

async def render_card_image(template_bytes: bytes, qr_data: str,
                             qr_x: int, qr_y: int, qr_size: int) -> bytes:
    return await asyncio.to_thread(
        _render_card_image_sync, template_bytes, qr_data, qr_x, qr_y, qr_size
    )
```

### Pattern 5: Public vs. Authenticated API Split

**What:** LNBits extensions have two classes of endpoints: (a) issuer/admin endpoints requiring `X-API-KEY` header via `require_admin_key` or `require_invoice_key`, and (b) public endpoints with no authentication (recipient pages, LNURL callbacks, QR image endpoints).

**When to use:** Always. Public gift card redemption must work for guests with no LNBits accounts.

**Example:**
```python
# views_api.py
cards_api_router = APIRouter(prefix="/api/v1/cards")
redeem_api_router = APIRouter(prefix="/api/v1")

# Issuer-only: requires admin key
@cards_api_router.post("")
async def api_create_card(
    data: CreateGiftCard,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> GiftCard: ...

# Public: no auth — recipient can redeem
@redeem_api_router.get("/lnurlw/{token}")
async def api_lnurlw_params(token: str, request: Request): ...
```

---

## Data Flow

### Gift Card Creation Flow (Single Card)

```
Issuer (browser)
    │
    ▼ POST /api/v1/cards  (admin_key)
views_api.py::api_create_card(data, wallet)
    │
    ▼ services.py::create_gift_card(data, wallet_id)
    │   ├── generate token = secrets.token_urlsafe(32)
    │   ├── crud.py::create_card(...)   → INSERT into giftcards.cards
    │   └── (optional) create_payment_request(wallet_id, amount)
    │        → returns bolt11 + payment_hash
    │
    ▼ Return GiftCard (with bolt11 for funding if pre-fund model)
    │
    ▼ tasks.py::on_invoice_paid  ← triggered when issuer pays bolt11
        └── mark_card_funded(card)
```

### Gift Card Redemption Flow (LNURL-Withdraw)

```
Recipient scans QR / opens link
    │
    ▼ GET /api/v1/lnurlw/{token}      (no auth)
views_api.py::lnurlw_params(token)
    │   ├── get_card_by_token(token)
    │   ├── validate: not redeemed, not expired
    │   └── return withdrawRequest JSON
    │
    ▼ Recipient wallet auto-calls callback URL
    │
    ▼ GET /api/v1/lnurlw/{token}/callback?pr={bolt11}&k1={token}
views_api.py::lnurlw_callback(token, pr)
    │   ├── crud.py::redeem_card_atomic(token)    ← atomic DB lock
    │   │    returns card | None (already redeemed)
    │   ├── if None → return {"status": "ERROR", "reason": "..."}
    │   └── core.services::pay_invoice(wallet_id=card.wallet, pr=pr)
    │
    ▼ Return {"status": "OK"}
    │
    ▼ (background) services.py::send_redemption_notification(card)
```

### Bulk Card Creation Flow (CSV Upload)

```
Issuer uploads CSV
    │
    ▼ POST /api/v1/cards/bulk  (admin_key, multipart)
views_api.py::api_create_cards_bulk(file, wallet)
    │
    ▼ asyncio.to_thread(parse_csv, file.file)  ← off event loop
    │   returns List[CreateGiftCard]
    │
    ▼ for each row:
    │   services.py::create_gift_card(row, wallet_id)  ← in loop
    │   (DB inserts are I/O-bound, remain async)
    │
    ▼ Return BatchResult(created=N, failed=K, cards=[...])
```

### State Machine

```
           ┌─────────┐
           │ CREATED │  ← card row inserted, token generated
           └────┬────┘
                │ (funding model A: direct debit from issuer wallet)
                │ mark_funded() immediately if balance check passes
                │
                │ (funding model B: issuer pays invoice)
                │ tasks.py::on_invoice_paid → mark_funded()
                ▼
           ┌─────────┐
           │  ACTIVE │  ← token valid, LNURL-withdraw enabled
           └────┬────┘
                │                          │
       redeem   │                          │ expiry_date < now
    (atomic)    ▼                          ▼
           ┌──────────┐             ┌─────────┐
           │ REDEEMED │             │ EXPIRED │
           └──────────┘             └─────────┘
```

**Recommended funding model:** Direct debit from issuer wallet at creation time (simpler, no invoice roundtrip). Verify wallet has sufficient balance before creating cards in bulk. Reserve funds atomically per card.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k cards total | Default monolith fine; SQLite works; image gen in `asyncio.to_thread()` |
| 1k-50k cards | Postgres recommended over SQLite (concurrent writes, WAL limits); add DB index on `token` and `wallet` columns |
| 50k+ cards | Index on `expires_at` for expiry sweeps; paginate admin dashboard queries; consider background cleanup task |

### Scaling Priorities

1. **First bottleneck:** Bulk image generation — CPU-bound PIL compositing blocks event loop. Fix: `asyncio.to_thread()` wrapping (already covered in Pattern 4).
2. **Second bottleneck:** SQLite write contention on bulk card creation. Fix: switch to PostgreSQL, or batch inserts inside a single transaction.
3. **Third bottleneck:** Redemption race condition at high concurrency. Fix: atomic DB UPDATE (Pattern 3 above) — always use this regardless of scale.

---

## Build Order Implications

The extension's components have natural dependency ordering for implementation:

```
Phase 1 (Foundation):
  config.json → __init__.py → migrations.py → models.py → crud.py

Phase 2 (Core API):
  views.py → views_api.py (CRUD endpoints) → tasks.py

Phase 3 (Redemption):
  services.py::redemption_logic → views_api.py::lnurlw_* endpoints
  (requires: models, crud, LNBits pay_invoice integration)

Phase 4 (Image + Delivery):
  services.py::image_gen → services.py::email_delivery
  (requires: PIL/pyqrcode, SMTP config, template images in static/)

Phase 5 (Bulk + UI):
  views_api.py::bulk_create → static/js/index.vue (admin dashboard)
  static/js/redeem.vue (public redemption page)
```

**Critical build constraint:** The LNURL-withdraw callback endpoint must be in place before any redemption testing. The callback URL is baked into the QR code at card creation — if the URL structure changes, old cards break.

---

## Anti-Patterns

### Anti-Pattern 1: Business Logic in `crud.py`

**What people do:** Put expiry checks, redemption validation, or notification logic inside CRUD functions to "keep it DRY."

**Why it's wrong:** CRUD functions are called by multiple services; embedding logic creates hidden coupling and makes unit testing impossible. The events extension pattern (`crud.py` = pure I/O, `services.py` = logic) is the canonical LNBits way.

**Do this instead:** Keep CRUD pure — `create_card()`, `get_card()`, `update_card()`. All business rules go in `services.py`.

---

### Anti-Pattern 2: Synchronous Read-Check-Write for Redemption

**What people do:**
```python
# WRONG — race condition
card = await get_card(token)
if card.redeemed:
    raise HTTPException(...)
card.redeemed = True
await update_card(card)   # another request got here first!
```

**Why it's wrong:** Two concurrent redemption requests can both read `redeemed=False` before either writes, leading to double-pay.

**Do this instead:** Single atomic `UPDATE ... WHERE redeemed = false RETURNING *`. If zero rows updated, card was already redeemed.

---

### Anti-Pattern 3: Blocking Image Generation on the Event Loop

**What people do:** Call `PIL.Image.open()`, `img.paste()`, `img.save()` directly in an `async def` endpoint.

**Why it's wrong:** PIL operations are CPU-bound and synchronous. They block the entire uvicorn event loop, serializing all requests during rendering.

**Do this instead:** Wrap all PIL calls in `await asyncio.to_thread(render_fn, ...)`. This offloads to a thread pool while the event loop remains responsive.

---

### Anti-Pattern 4: Using `payment_hash` as the Redemption Token

**What people do:** Use the LNBits payment hash as the gift card token embedded in the QR code.

**Why it's wrong:** Payment hashes are derived from invoice data and are not sufficiently random for use as a standalone unguessable secret. They also couple the gift card identity to a specific funding invoice.

**Do this instead:** Generate a separate `token = secrets.token_urlsafe(32)` at card creation. Store it in the card record. Payment hash is an internal funding detail only.

---

### Anti-Pattern 5: Storing Email Addresses Beyond Delivery Need

**What people do:** Store recipient email in the card record as a permanent attribute, expose it in list endpoints.

**Why it's wrong:** The PROJECT.md explicitly flags privacy — recipient email is delivery-only. Exposing it in list APIs leaks PII to API key holders who only need to know card status.

**Do this instead:** Store email in a separate `extra` JSON blob or nullable column; exclude it from public/list API response models (use `PublicGiftCard` model that omits PII fields).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LNBits Core (`pay_invoice`) | `from lnbits.core.services import pay_invoice` — direct import | Used at redemption to pay recipient's wallet; requires issuer wallet has sufficient balance |
| LNBits Core (`create_payment_request`) | `from lnbits.core.services import create_payment_request` | Used in pre-fund model to generate bolt11 for issuer to pay |
| LNBits Core (invoice listener) | `from lnbits.tasks import register_invoice_listener` | Async queue subscription in `tasks.py` |
| SMTP email | `smtplib.SMTP` via `lnbits.settings` — matches events extension pattern | Requires `lnbits_email_notifications_enabled` setting |
| Nostr DM | `lnbits.core.services.notifications.send_user_notification` | Requires nostr config; optional |
| PIL / Pillow | Direct Python import — already a LNBits dependency (used in events) | Image compositing for gift card PNG generation |
| pyqrcode | Direct Python import — already used in events extension | QR code matrix generation |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `views_api.py` ↔ `services.py` | Direct async function calls | `views_api.py` handles auth + HTTP concerns only; delegates logic to services |
| `services.py` ↔ `crud.py` | Direct async function calls | Services compose CRUD operations; CRUD never imports services |
| `tasks.py` ↔ `crud.py` | Direct async function calls | Invoice handler updates card state via CRUD |
| `tasks.py` ↔ `views_api.py` | Shared `payment_listeners` dict (module-level) | WebSocket push: API registers queue, tasks notifies it |
| Extension ↔ LNBits Core | Imports from `lnbits.core.*` and `lnbits.*` | Do NOT call LNBits core REST endpoints from within the same process — import directly |

---

## Sources

- Live codebase: `/home/exedev/events/` — events extension (primary structural reference) [MEDIUM confidence — production extension in workspace]
- Live codebase: `/home/exedev/lnbits/lnbits/extensions/tpos/`, `satspay/`, `paywall/` — additional extension patterns [MEDIUM confidence]
- Live codebase: `/home/exedev/lnbits/lnbits/core/services/payments.py` — `pay_invoice`, `create_payment_request` API [MEDIUM confidence]
- Live codebase: `/home/exedev/lnbits/lnbits/core/services/lnurl.py` — `execute_withdraw`, `perform_withdraw` [MEDIUM confidence]
- LNBits docs: https://docs.lnbits.com/extensions/withdraw/ — LNURL-withdraw / voucher pattern [LOW confidence — web source]
- LNBits docs: https://docs.lnbits.com/guide/core/lnurl/overview — LNURL protocol support [LOW confidence — web source]

---
*Architecture research for: LNBits Gift Cards Extension*
*Researched: 2026-06-29*
