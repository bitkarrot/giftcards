# Phase 1: Core Loop - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `giftcards/__init__.py` | bootstrap | event-driven | `/home/exedev/events/__init__.py` | exact |
| `giftcards/models.py` | model | CRUD | `/home/exedev/events/models.py` | exact |
| `giftcards/migrations.py` | migration | file-I/O | `/home/exedev/events/migrations.py` | exact |
| `giftcards/crud.py` | service | CRUD | `/home/exedev/events/crud.py` | exact |
| `giftcards/services.py` | service | event-driven | `/home/exedev/events/services.py` | role-match |
| `giftcards/views_api.py` | controller | request-response | `/home/exedev/events/views_api.py` | exact |
| `giftcards/views.py` | controller | request-response | `/home/exedev/events/views.py` | exact |
| `giftcards/tasks.py` | service | event-driven | `/home/exedev/events/tasks.py` | role-match |
| `giftcards/static/js/redeem.vue` | component | request-response | `/home/exedev/events/static/js/ticket.vue` | role-match |

## Pattern Assignments

### `giftcards/__init__.py` (bootstrap, event-driven)

**Analog:** `/home/exedev/events/__init__.py`

**Extension bootstrap pattern** (lines 1-42):
```python
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

giftcards_static_files = [
    {
        "path": "/giftcards/static",
        "name": "giftcards_static",
    }
]

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

**Key export names:** `{ext_id}_ext`, `{ext_id}_start`, `{ext_id}_stop`, `{ext_id}_static_files`, `db`

---

### `giftcards/models.py` (model, CRUD)

**Analog:** `/home/exedev/events/models.py`

**Pydantic v1 model pattern** (lines 1-25):
```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

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
    wallet: str
    card_wallet_id: Optional[str]
    amount: int
    token_hash: str
    status: str = "active"
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_at: Optional[datetime]
    expired_at: Optional[datetime]
```

**Pydantic v1 rules:** Use `Optional[X]` not `X | None`, use `validator` decorator, use `model.dict()` not `model.model_dump()`

---

### `giftcards/migrations.py` (migration, file-I/O)

**Analog:** `/home/exedev/events/migrations.py`

**Initial migration pattern** (lines 1-21):
```python
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
    # Index for expiry sweep
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_giftcards_cards_status_expires ON giftcards.cards (status, expires_at);"
    )
```

**DB-agnostic timestamp:** Use `db.timestamp_now` for DDL, `db.timestamp_placeholder('key')` for DML

---

### `giftcards/crud.py` (service, CRUD)

**Analog:** `/home/exedev/events/crud.py`

**Database setup and CRUD pattern** (lines 1-36):
```python
from datetime import datetime, timezone
from typing import cast

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import GiftCard, CreateGiftCard

db = Database("ext_giftcards")

async def create_gift_card(card: GiftCard) -> GiftCard:
    await db.insert("giftcards.cards", card)
    return card

async def get_gift_card(card_id: str) -> GiftCard | None:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE id = :id",
        {"id": card_id},
        GiftCard,
    )

async def get_cards_by_wallet(wallet_id: str) -> list[GiftCard]:
    return await db.fetchall(
        "SELECT * FROM giftcards.cards WHERE wallet = :wallet",
        {"wallet": wallet_id},
        GiftCard,
    )
```

**ORM helpers:** `db.insert()` for create, `db.fetchone()` for read, `db.fetchall()` for list, `db.update()` for update

---

### `giftcards/services.py` (service, event-driven)

**Analog:** `/home/exedev/events/services.py`

**Business logic pattern** (lines 1-50):
```python
import hashlib
import secrets
from datetime import datetime, timezone

from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.services.payments import update_wallet_balance
from lnbits.helpers import urlsafe_short_hash
from loguru import logger

from .crud import create_gift_card as crud_create_card
from .models import CreateGiftCard, GiftCard

async def create_gift_card(
    data: CreateGiftCard,
    issuer_wallet_id: str,
    user_id: str,
) -> GiftCard:
    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    card_id = urlsafe_short_hash()

    # Create dedicated card wallet (D-03)
    card_wallet = None
    try:
        card_wallet = await create_wallet(
            user_id=user_id,
            wallet_name=f"GiftCard {card_id[:8]}",
        )
    except Exception:
        logger.warning(f"Dedicated wallet creation failed for {card_id}")

    # Create DB record
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

    # Debit issuer wallet
    issuer_wallet = await get_wallet(issuer_wallet_id)
    await update_wallet_balance(issuer_wallet, -data.amount)
    if card_wallet:
        card_wallet_obj = await get_wallet(card_wallet.id)
        await update_wallet_balance(card_wallet_obj, data.amount)

    return card
```

**Key imports:** `create_wallet` for dedicated wallets, `update_wallet_balance` for debit/credit, `secrets` + `hashlib` for tokens

---

### `giftcards/views_api.py` (controller, request-response)

**Analog:** `/home/exedev/events/views_api.py`

**Auth pattern** (lines 26-30, 168):
```python
from lnbits.decorators import require_admin_key
from lnbits.core.models import WalletTypeInfo

@events_api_router.post("")
async def api_event_create(
    data: CreateEvent,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> Event:
    # ALWAYS derive wallet_id from the decorator, NEVER from data
    wallet_id = wallet.wallet.id
    user_id = wallet.wallet.user   # needed for create_wallet
    return await create_event(data, wallet_id, user_id)
```

**LNURL-withdraw pattern** (from `/home/exedev/lnbits/lnbits/extensions/tpos/views_lnurl.py` lines 46-82):
```python
from lnurl import (
    CallbackUrl,
    LnurlErrorResponse,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
    MilliSatoshi,
)
from pydantic import parse_obj_as

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
```

**Auth contract:** `wallet.wallet.id` for wallet scoping, `wallet.wallet.user` for user ID, never accept from request body

---

### `giftcards/views.py` (controller, request-response)

**Analog:** `/home/exedev/events/views.py`

**Public redemption page pattern** (lines 1-20):
```python
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

**Key pattern:** `index_public` serves SPA without authentication, raw token in URL handled client-side by Vue

---

### `giftcards/tasks.py` (service, event-driven)

**Analog:** `/home/exedev/events/tasks.py` + `/home/exedev/lnbits/lnbits/tasks.py`

**Background task registration pattern** (lines 152-167):
```python
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

**Key helpers:** `create_permanent_unique_task` for crash recovery, `run_interval(60, func)` for periodic execution

---

### `giftcards/static/js/redeem.vue` (component, request-response)

**Analog:** `/home/exedev/events/static/js/ticket.vue`

**Vue SPA pattern** (structure):
```vue
<template>
  <div class="redeem-container">
    <!-- Card details display -->
    <!-- LNURL-withdraw QR code -->
    <!-- Redemption status -->
  </div>
</template>

<script>
export default {
  name: "RedeemGiftCard",
  data() {
    return {
      card: null,
      loading: false,
      error: null,
    };
  },
  async mounted() {
    // Extract raw_token from URL
    // Fetch card details from public API
    // Generate LNURL-withdraw QR
  },
  methods: {
    async fetchCard() {
      // GET /giftcards/api/v1/lnurl/{token_hash}
    },
    generateQR() {
      // Use QR code library to encode LNURL URL
    },
  },
};
</script>
```

**Key pattern:** Guest access, raw token from URL, public API calls, QR code generation

---

## Shared Patterns

### Authentication
**Source:** `/home/exedev/events/views_api.py` lines 26-30
**Apply to:** All controller files with admin endpoints
```python
from lnbits.decorators import require_admin_key
from lnbits.core.models import WalletTypeInfo

@router.post("")
async def api_create(
    data: CreateModel,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> Model:
    wallet_id = wallet.wallet.id  # Derive from decorator
    user_id = wallet.wallet.user  # For create_wallet calls
```

### Database Operations
**Source:** `/home/exedev/events/crud.py` lines 16-36
**Apply to:** All CRUD operations
```python
from lnbits.db import Database

db = Database("ext_giftcards")

# Create
await db.insert("giftcards.cards", model)

# Read one
await db.fetchone("SELECT * FROM giftcards.cards WHERE id = :id", {"id": id}, Model)

# Read many
await db.fetchall("SELECT * FROM giftcards.cards WHERE wallet = :wallet", {"wallet": wallet}, Model)

# Update
await db.update("giftcards.cards", model)
```

### Error Handling
**Source:** `/home/exedev/events/views_api.py` lines 176-179
**Apply to:** All controller endpoints
```python
from fastapi import HTTPException
from http import HTTPStatus

if not event:
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, 
        detail="Event does not exist."
    )
```

### Background Tasks
**Source:** `/home/exedev/events/tasks.py` lines 27-34
**Apply to:** Background task files
```python
from lnbits.tasks import register_invoice_listener

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_giftcards")
    
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)
```

## No Analog Found

All files have close matches in the codebase. No patterns require external research.

## Metadata

**Analog search scope:** `/home/exedev/events/`, `/home/exedev/lnbits/lnbits/extensions/tpos/`, `/home/exedev/lnbits/lnbits/core/`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-29