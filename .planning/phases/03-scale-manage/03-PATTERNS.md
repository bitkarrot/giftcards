# Phase 3: Scale & Manage - Pattern Map

**Mapped:** 2026-06-30
**Files analyzed:** 7 (6 modified, 1 new)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `views_api.py` (modify) | controller | request-response | `views_api.py` (existing endpoints) + `/home/exedev/events/views_api.py` | exact |
| `models.py` (modify) | model | request-response | `models.py` (existing `CreateGiftCard`, `DeliverRequest`) | exact |
| `crud.py` (modify) | service | CRUD | `crud.py` (existing `get_cards_by_wallet`, `update_card_email_status`) + `/home/exedev/events/crud.py` | exact |
| `services.py` (modify) | service | batch / transform | `services.py` (existing `create_gift_card`, `reclaim_card_sats`) | exact |
| `migrations.py` (modify) | migration | transform | `migrations.py` (existing `m001`–`m003`) | exact |
| `static/js/index.vue` (modify) | component | request-response | `static/js/index.vue` (existing create/email dialogs, q-table) | exact |
| `static/js/index.js` (modify) | component | request-response | `static/js/index.js` (existing `createGiftCard`, `loadGiftCards`, `exportCSV`) | exact |

## Pattern Assignments

### `views_api.py` (controller, request-response) — MODIFY

**Analog:** `views_api.py` existing endpoints (lines 55-85, 296-343) + `/home/exedev/events/views_api.py` (lines 152-168, 210-289)

**Imports pattern** (lines 1-52) — add `require_invoice_key` and `UploadFile`/`Query`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key, require_invoice_key
```

**Existing create endpoint — copy for bulk create** (lines 55-72):
```python
@giftcards_api_router.post("")
async def api_create_card(
    data: CreateGiftCard,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Create a new gift card."""
    try:
        response = await create_gift_card(
            data=data,
            issuer_wallet_id=wallet.wallet.id,
            user_id=wallet.wallet.user,
            base_url=str(request.base_url),
        )
        return response.dict()
    except Exception as e:
        logger.error(f"Failed to create gift card: {e}")
        raise HTTPException(status_code=500, detail="Failed to create gift card")
```

**Existing list endpoint — switch to invoice key + add query params** (lines 75-85):
```python
@giftcards_api_router.get("")
async def api_get_cards(
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> list[GiftCardSummary]:
    """Get all gift cards for the authenticated wallet."""
    try:
        cards = await get_cards_by_wallet(wallet.wallet.id)
        return cards
    except Exception as e:
        logger.error(f"Failed to get cards: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cards")
```

**Mixed-auth pattern (events extension)** — `/home/exedev/events/views_api.py` lines 152-168 (reads use `require_invoice_key`, writes use `require_admin_key`):
```python
@events_api_router.get("")
async def api_events(
    all_wallets: bool = Query(False),
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> list[Event]:
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []
    return await get_events(wallet_ids)
```

**Delete endpoint pattern (events extension)** — `/home/exedev/events/views_api.py` lines 266-281 (ownership check + delete):
```python
@events_api_router.delete("/{event_id}")
async def api_form_delete(
    event_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
) -> None:
    event = await get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Event does not exist."
        )
    if event.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your event.")
    await delete_event(event_id)
    await delete_event_tickets(event_id)
```

**Existing deliver endpoint — ownership check + service call** (lines 296-343) — copy for update endpoint:
```python
@giftcards_api_router.post("/{card_id}/deliver")
async def api_deliver_email(
    card_id: str,
    data: DeliverRequest,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")
    if card.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Card does not belong to this wallet")
    # ... service call + error handling ...
```

**StreamingResponse for CSV export** (lines 226-234, 251-259) — existing PNG pattern, reuse for CSV:
```python
return StreamingResponse(
    output,
    media_type="image/png",
    headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    },
)
```

**Error handling pattern** (lines 70-72, 337-343) — logger + generic HTTPException, never leak internals:
```python
except Exception as e:
    logger.error(f"Failed to create gift card: {e}")
    raise HTTPException(status_code=500, detail="Failed to create gift card")
```

---

### `models.py` (model, request-response) — MODIFY

**Analog:** `models.py` existing models (`CreateGiftCard` lines 119-156, `DeliverRequest` lines 105-116, `GiftCardSummary` lines 186-199)

**Pydantic v1 BaseModel + `@validator` pattern** (lines 119-137):
```python
class CreateGiftCard(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in sats")
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        return _normalize_email(v)
```

**Email normalization helper** (lines 14-18) — reuse for CSV row + update models:
```python
def _normalize_email(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    return v.strip().lower()
```

**Date parsing validator** (lines 139-156) — reuse for CSV row `expires_at` if added:
```python
@validator("expires_at", pre=True)
def parse_expires_at(cls, v):
    if v is None or v == "":
        return None
    if isinstance(v, str):
        if len(v) == 10 and v.count("-") == 2:
            return datetime.fromisoformat(v + "T23:59:59+00:00")
        try:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return v
```

**Summary/response model pattern** (lines 186-199, 213-217) — copy for `CardDetailResponse` with optional `redemption_url`:
```python
class GiftCardSummary(BaseModel):
    id: str
    amount: int
    status: str
    recipient_name: Optional[str]
    # ...
    redemption_url: Optional[str] = None
    recipient_email: Optional[str] = None
    email_status: Optional[str] = None

class CreateGiftCardResponse(BaseModel):
    card: GiftCardSummary
    raw_token: str
    redemption_url: str
    lnurl_url: str
```

**New models to add (following same patterns):**
- `BulkCreateRequest` — `amount`, `count` (Field gt=0, le=500), optional `recipient_name`/`sender_name`/`message`/`expires_at`/`recipient_email`/`design`
- `CSVRow` — `recipient_name` (required), `amount_sats` (required, gt=0), optional `recipient_email`/`nostr_npub`/`sender_name`/`message` + design columns; `@validator` for email normalization
- `CSVValidationResult` — `row_index`, `valid`, `errors: list[str]`, parsed fields
- `UpdateCardRequest` — `recipient_name`/`sender_name`/`message`/`recipient_email` (all optional, no amount field)
- `CardDetailResponse` — extends `GiftCardSummary` with `redemption_url: Optional[str] = None` (populated only when `?include_link=true`)

---

### `crud.py` (service, CRUD) — MODIFY

**Analog:** `crud.py` existing functions + `/home/exedev/events/crud.py` (update/delete patterns)

**DB setup + query pattern** (lines 1-40):
```python
from lnbits.db import Database
from .models import GiftCard, GiftCardSummary
db = Database("ext_giftcards")

async def get_cards_by_wallet(wallet_id: str) -> list[GiftCardSummary]:
    return await db.fetchall(
        "SELECT id, amount, status, recipient_name, sender_name, message, expires_at, created_at, redeemed_at, expired_at, redemption_url, recipient_email, email_status FROM giftcards.cards WHERE wallet = :wallet",
        {"wallet": wallet_id},
        GiftCardSummary,
    )
```

**Filtered query pattern** — extend `get_cards_by_wallet` with optional WHERE clauses (status, search, date range). Use parameterized queries with `db.timestamp_placeholder()` for dates (see lines 63-69, 85-94):
```python
async def mark_redeemed(card_id: str) -> None:
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'redeemed', redeemed_at = {db.timestamp_placeholder('now')}
        WHERE id = :id
        """,
        {"id": card_id, "now": time.time()},
    )
```

**Update column pattern** (lines 111-132) — copy for `update_card()`:
```python
async def update_card_email_status(card_id: str, status: str) -> None:
    await db.execute(
        """
        UPDATE giftcards.cards
        SET email_status = :status
        WHERE id = :id
        """,
        {"id": card_id, "status": status},
    )

async def update_card_recipient_email(card_id: str, email: str) -> None:
    await db.execute(
        """
        UPDATE giftcards.cards
        SET recipient_email = :email
        WHERE id = :id
        """,
        {"id": card_id, "email": email},
    )
```

**Delete pattern (events extension)** — `/home/exedev/events/crud.py` line 142:
```python
async def delete_event(event_id: str) -> None:
    await db.execute("DELETE FROM events.events WHERE id = :id", {"id": event_id})
```

**`db.update()` helper (events extension)** — `/home/exedev/events/crud.py` line 118 (alternative to manual UPDATE SQL):
```python
async def update_event(event: Event) -> Event:
    await db.update("events.events", event)
    return event
```

**Atomic conditional update pattern** (lines 43-57, 84-94) — copy for reclaim-on-delete guard:
```python
async def mark_redeeming(token_hash: str) -> Optional[GiftCard]:
    result = await db.execute(
        """
        UPDATE giftcards.cards 
        SET status = 'redeeming' 
        WHERE token_hash = :hash AND status = 'active'
        """,
        {"hash": token_hash},
    )
    if result.rowcount == 0:
        return None
    return await get_card_by_token_hash(token_hash)
```

**New CRUD functions to add:**
- `get_cards_by_wallet_filtered(wallet_id, status=None, search=None, date_from=None, date_to=None)` — build dynamic WHERE clause with parameterized values
- `update_card(card_id, **fields)` — update recipient_name/sender_name/message/recipient_email
- `delete_card(card_id)` — `DELETE FROM giftcards.cards WHERE id = :id`

---

### `services.py` (service, batch / transform) — MODIFY

**Analog:** `services.py` existing `create_gift_card()` (lines 39-136), `reclaim_card_sats()` (lines 165-179)

**Bulk creation inner loop — reuse `create_gift_card()`** (lines 39-136):
```python
async def create_gift_card(
    data: CreateGiftCard, issuer_wallet_id: str, user_id: str, base_url: str
) -> CreateGiftCardResponse:
    raw_token, token_hash = generate_token()
    card_id = f"gc_{token_hash[:16]}"
    # ... serialize design config, build GiftCard, await create_card(card) ...
    # Debit issuer wallet immediately
    issuer_wallet = await get_wallet(issuer_wallet_id)
    if issuer_wallet:
        await update_wallet_balance(wallet=issuer_wallet, amount=-data.amount)
    # Build response with redemption_url + lnurl_url
    return CreateGiftCardResponse(...)
```

**Sats reclaim pattern** (lines 165-179) — wrap for `reclaim_sats_and_delete()`:
```python
async def reclaim_card_sats(card: GiftCard) -> None:
    issuer_wallet = await get_wallet(card.wallet)
    if not issuer_wallet:
        logger.error(f"Cannot reclaim sats for expired card {card.id}: issuer wallet not found")
        return
    try:
        await update_wallet_balance(wallet=issuer_wallet, amount=card.amount)
    except Exception as exc:
        logger.error(f"Reclaim failed for expired card {card.id}: {exc}")
```

**Imports pattern** (lines 1-20) — add `csv`, `io.StringIO` for CSV parsing:
```python
import asyncio
import csv
import hashlib
import json
import secrets
from datetime import datetime, timezone
from io import BytesIO, StringIO
from lnbits.core.services.payments import update_wallet_balance
from .crud import create_card, get_card_by_token_hash, delete_card, reclaim_card_sats
from .models import CreateGiftCard, GiftCard, DesignConfig, CSVRow
```

**Async offload pattern** (lines 356-358, 452-454) — for CSV parse / bulk email:
```python
return await asyncio.to_thread(
    _render_card_image_sync, card, lnurl_url, scale, template_bytes
)
# ...
await asyncio.to_thread(
    _send_smtp_email, recipient_email, subject, text_body, html_body
)
```

**Fire-and-forget background task pattern** (`views_api.py` lines 379-386) — for bulk email send:
```python
asyncio.create_task(
    _send_notification_safely(
        sender_name=...,
        recipient_email=...,
        claim_url=...,
        magic_link_url=...,
    )
)
```

**Email send + status update pattern** (lines 457-509) — reuse for bulk "Send all":
```python
async def send_gift_card_email(card, claim_url, email_mode, ...):
    # ... render template, send via asyncio.to_thread(_send_smtp_email, ...) ...
    try:
        await asyncio.to_thread(_send_smtp_email, card.recipient_email, subj, text_body, html_body)
        await update_card_email_status(card.id, "sent")
    except Exception as exc:
        logger.warning(f"Email delivery failed for card {card.id[:8]}: {exc}")
        await update_card_email_status(card.id, "failed")
        raise
```

**New service functions to add:**
- `parse_csv(file_bytes) -> list[dict]` — `csv.DictReader` on `StringIO`, stdlib only (no pandas)
- `validate_csv_rows(rows) -> list[CSVValidationResult]` — validate each row against `CSVRow` Pydantic model, collect errors
- `bulk_create_with_funding(rows, wallet_id, user_id, base_url, design=None)` — loop `create_gift_card()` per row, handle partial failures
- `reclaim_sats_and_delete(card)` — call `reclaim_card_sats()` if status == 'active', then `delete_card()`
- `export_cards_csv(cards) -> bytes` — build CSV string with all card fields

---

### `migrations.py` (migration, transform) — MODIFY

**Analog:** `migrations.py` existing `m001_initial` (lines 1-35), `m002_add_raw_token` (lines 38-45), `m003_branded_delivery` (lines 48-85)

**Sequential migration pattern** (lines 38-45):
```python
async def m002_add_raw_token(db):
    """Store raw_token and redemption_url so links can be retrieved later by the issuer."""
    await db.execute(
        "ALTER TABLE giftcards.cards ADD COLUMN raw_token TEXT"
    )
    await db.execute(
        "ALTER TABLE giftcards.cards ADD COLUMN redemption_url TEXT"
    )
```

**Index creation pattern** (lines 23-35, 79-85) — for dashboard filter performance:
```python
table = f"{db.references_schema}cards"
await db.execute(
    f"""
    CREATE INDEX IF NOT EXISTS idx_giftcards_cards_wallet ON {table}(wallet);
    """
)
await db.execute(
    f"""
    CREATE INDEX IF NOT EXISTS idx_giftcards_cards_status_expires ON {table}(status, expires_at);
    """
)
```

**New migration `m004_dashboard_indexes` (likely):**
- Add index on `(wallet, status, created_at)` for filtered dashboard queries
- Optionally add `updated_at TIMESTAMP` column if edit tracking needed
- The `status` column already accepts arbitrary strings (TEXT), so `cancelled` status needs no schema change — only an index for filter performance

---

### `static/js/index.vue` (component, request-response) — MODIFY

**Analog:** `static/js/index.vue` existing create dialog (lines 202-464), email dialog (lines 473-577), q-table (lines 30-161)

**Dialog pattern** (lines 202-205) — copy for bulk/detail/edit/delete dialogs:
```html
<q-dialog v-model="createDialog.show" position="top">
  <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
    <q-form @submit="createGiftCard">
      <div class="q-gutter-md">
        <!-- ... form fields ... -->
      </div>
    </q-form>
  </q-card>
</q-dialog>
```

**CTA button pattern** (lines 4-13) — add "Bulk Create" button next to existing:
```html
<q-card>
  <q-card-section>
    <q-btn
      unelevated
      color="primary"
      label="Create Gift Card"
      @click="openCreateDialog"
    ></q-btn>
  </q-card-section>
</q-card>
```

**q-table with expand row** (lines 30-161) — add `selection="multiple"`, `v-model:selected`, filter bar above:
```html
<q-table
  dense
  flat
  :rows="giftCards"
  row-key="id"
  :columns="giftCardColumns"
  v-model:pagination="tablePagination"
  :loading="loading"
>
  <template v-slot:body="props">
    <q-tr :props="props">
      <q-td auto-width>
        <q-btn size="sm" color="accent" round dense
          @click="props.expand = !props.expand"
          :icon="props.expand ? 'expand_less' : 'expand_more'"
        ></q-btn>
      </q-td>
      <!-- ... columns ... -->
    </q-tr>
    <q-tr v-show="props.expand" :props="props">
      <q-td colspan="100%">
        <!-- expanded row content + action buttons -->
      </q-td>
    </q-tr>
  </template>
</q-table>
```

**Form field pattern** (lines 207-266) — `q-select`/`q-input` with `filled dense`, `:rules` validation:
```html
<q-input
  filled
  dense
  v-model.number="createDialog.data.amount"
  type="number"
  label="Amount (sats)"
  hint="Sats will be locked from your wallet at creation."
  :rules="[
    val => val > 0 || 'Amount must be greater than 0',
    val => val <= walletBalance || 'Amount exceeds your wallet balance'
  ]"
></q-input>
```

**Card designer UI** (lines 268-394) — reusable block for bulk "One design for all" mode (template select, drag preview, font/size/color/alignment controls). Extract or duplicate into bulk dialog's `v-if="designMode === 'shared'"` section.

**Status badge pattern** (lines 62-67) — extend `getStatusColor`/`getStatusText` for `created`/`cancelled`:
```html
<q-badge
  :color="getStatusColor(col.value)"
  :label="getStatusText(col.value)"
></q-badge>
```

**Dark mode color pattern** (line 87) — use `$q.dark.isActive` ternary, never hardcode hex:
```html
:color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
```

**New template sections to add:**
- Bulk Create button in CTA card (Screen 1)
- Bulk Create dialog with `q-tabs`/`q-tab-panels` (Same Amount + CSV Upload tabs) (Screen 2)
- Filter bar (status `q-select`, search `q-input`, date range `q-popup-proxy` + `q-date`) above table (Screen 3)
- Multi-select (`selection="multiple"`, `v-model:selected="selectedCards"`) + bulk action buttons (Screen 4)
- Expanded row: add "View Full Details" / "Edit" / "Delete" buttons (Screen 4)
- Card detail dialog (Screen 5)
- Card edit dialog (Screen 6)
- Delete confirmation dialog (Screen 7)

---

### `static/js/index.js` (component, request-response) — MODIFY

**Analog:** `static/js/index.js` existing methods (`loadGiftCards` lines 161-175, `createGiftCard` lines 236-278, `exportCSV` lines 368-400, `sendEmail` lines 591-615)

**API request pattern** (lines 161-175) — copy for all new endpoints (bulk, update, delete, filtered list):
```javascript
async loadGiftCards() {
  this.loading = true
  try {
    const response = await LNbits.api.request(
      'GET',
      '/giftcards/api/v1/cards',
      this.g.user.wallets[0].adminkey
    )
    this.giftCards = response.data || []
  } catch (error) {
    LNbits.utils.notifyApiError(error)
  } finally {
    this.loading = false
  }
},
```

**POST with payload pattern** (lines 236-278) — copy for bulk create, update:
```javascript
async createGiftCard() {
  this.createDialog.loading = true
  try {
    const wallet = this.g.user.wallets.find(w => w.id === this.createDialog.data.wallet)
    const payload = { ...this.createDialog.data, design: designConfig }
    const response = await LNbits.api.request(
      'POST',
      '/giftcards/api/v1/cards',
      wallet.adminkey,
      payload
    )
    this.createDialog.result = response.data
    this.loadGiftCards()
    this.loadWalletBalance()
    LNbits.utils.notify('Gift card created successfully!', 'positive')
  } catch (error) {
    LNbits.utils.notifyApiError(error)
  } finally {
    this.createDialog.loading = false
  }
},
```

**File download pattern** (lines 343-366) — copy for CSV template download, CSV export:
```javascript
async downloadPrintable(card) {
  try {
    const wallet = this.g.user.wallets.find(w => w.id === card.wallet) || this.g.user.wallets[0]
    const url = `/giftcards/api/v1/cards/${card.id}/print`
    const response = await fetch(url, {
      headers: { 'X-Api-Key': wallet.adminkey }
    })
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `giftcard_${card.id}.png`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(downloadUrl)
    LNbits.utils.notify('Gift card image downloaded', 'positive')
  } catch (error) {
    LNbits.utils.notifyApiError(error)
  }
},
```

**Client-side CSV export pattern** (lines 368-400) — existing manual CSV builder, or use `LNbits.utils.exportCSV`:
```javascript
exportCSV() {
  const headers = ['ID', 'Amount (sats)', 'Recipient', 'Sender', 'Message', 'Status', 'Created', 'Expires']
  const rows = this.giftCards.map(card => [...])
  let csv = headers.join(',') + '\n'
  rows.forEach(row => { csv += row.map(cell => `"${cell}"`).join(',') + '\n' })
  const blob = new Blob([csv], { type: 'text/csv' })
  // ... download via anchor click ...
}
```

**`LNbits.utils.exportCSV` helper** — `/home/exedev/lnbits/lnbits/static/js/utils.js` line 273 (alternative, used by events extension):
```javascript
LNbits.utils.exportCSV(columns, data, fileName)
// Wraps values in quotes, handles format fns, uses Quasar.exportFile
```

**Email validation helper** (lines 573-577) — reuse in edit dialog:
```javascript
isValidEmail(val) {
  if (!val) return false
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(val)
},
```

**Status color/text helpers** (lines 307-341) — extend for `created`/`cancelled`:
```javascript
getStatusColor(status) {
  switch (status) {
    case 'active': return 'positive'
    case 'redeemed': return 'grey-6'
    case 'expired': return 'warning'
    default: return 'grey'
  }
},
```

**File upload pattern** (lines 558-569) — `FormData` + `LNbits.api.request` for CSV upload:
```javascript
async uploadAssetFile(file) {
  const form = new FormData()
  form.append('file', file)
  form.append('public_asset', 'true')
  const {data} = await LNbits.api.request(
    'POST',
    '/api/v1/assets?public_asset=true',
    null,
    form
  )
  return data.id
},
```

**New JS methods/data to add:**
- `bulkDialog` data object (show, loading, activeTab, sameData, csvData, csvFile, csvRows, csvErrors)
- `dashboardFilters` data (status, search, dateFrom, dateTo)
- `selectedCards` array (v-model:selected)
- `detailDialog`, `editDialog`, `deleteDialog` data objects
- Methods: `openBulkDialog`, `submitBulkCreate`, `onCsvFileSelected`, `downloadCsvTemplate`, `applyFilters`, `clearFilters`, `sendBulkEmails`, `exportCSV(scope)`, `openDetailDialog`, `openEditDialog`, `saveCardEdit`, `openDeleteDialog`, `confirmDelete`
- Computed: `csvValidationColumns`, `statusFilterOptions`, `anyFilterActive`, `bulkSubmitLabel`, `bulkSubmitDisabled`, `filteredGiftCards`

## Shared Patterns

### Authentication (Admin Key for Writes, Invoice Key for Reads)
**Source:** `views_api.py` lines 59, 77 + `/home/exedev/lnbits/lnbits/decorators.py` lines 180-225 + `/home/exedev/events/views_api.py` lines 155, 214, 268
**Apply to:** All new/modified endpoints in `views_api.py`
```python
from lnbits.decorators import require_admin_key, require_invoice_key

# Writes (create, bulk create, update, delete):
wallet: WalletTypeInfo = Depends(require_admin_key)

# Reads (list, detail, status):
wallet: WalletTypeInfo = Depends(require_invoice_key)
```

### Ownership Check (Wallet Scoping)
**Source:** `views_api.py` lines 315-316 + `/home/exedev/events/views_api.py` lines 275-277
**Apply to:** All card-specific endpoints (update, delete, deliver, detail)
```python
card = await get_card(card_id)
if not card:
    raise HTTPException(status_code=404, detail="Gift card not found")
if card.wallet != wallet.wallet.id:
    raise HTTPException(status_code=403, detail="Card does not belong to this wallet")
```

### Error Handling (Logger + Generic HTTPException)
**Source:** `views_api.py` lines 70-72, 337-343
**Apply to:** All new endpoints
```python
except Exception as e:
    logger.error(f"Failed to {action}: {e}")
    raise HTTPException(status_code=500, detail="Failed to {action}")
# For SMTP/email (never leak internals):
except Exception as exc:
    logger.warning(f"Email delivery failed for card {card.id[:8]}: {exc}")
    raise HTTPException(status_code=500, detail="Email delivery failed. Check server logs.")
```

### Pydantic v1 Validation
**Source:** `models.py` lines 5, 119-156
**Apply to:** All new request models (`BulkCreateRequest`, `CSVRow`, `UpdateCardRequest`)
```python
from pydantic import BaseModel, Field, validator
# Use Field(..., gt=0) for amounts, @validator for email normalization + custom rules
# NEVER use Pydantic v2 syntax (model_validator, field_validator) — LNBits 1.5.x is v1
```

### DB Query Parameterization
**Source:** `crud.py` lines 20-40, 63-69
**Apply to:** All new CRUD functions (filtered query, update, delete)
```python
await db.fetchall(
    "SELECT ... FROM giftcards.cards WHERE wallet = :wallet AND status = :status",
    {"wallet": wallet_id, "status": status},
    GiftCardSummary,
)
# Timestamps use db.timestamp_placeholder():
f"created_at > {db.timestamp_placeholder('date_from')}"
```

### Frontend API Call + Notify
**Source:** `static/js/index.js` lines 161-175, 236-278
**Apply to:** All new JS methods calling new endpoints
```javascript
try {
  const response = await LNbits.api.request('METHOD', '/giftcards/api/v1/cards/...', wallet.adminkey, payload)
  LNbits.utils.notify('Success message', 'positive')
  this.loadGiftCards()
} catch (error) {
  LNbits.utils.notifyApiError(error)
} finally {
  this.someDialog.loading = false
}
```

### Quasar Dialog Pattern
**Source:** `static/js/index.vue` lines 202-205, 473-476
**Apply to:** All new dialogs (bulk, detail, edit, delete)
```html
<q-dialog v-model="dialogName.show" position="top">
  <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
    <q-form @submit="submitHandler">
      <div class="q-gutter-md"><!-- fields --></div>
    </q-form>
  </q-card>
</q-dialog>
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All files have strong analogs in the existing codebase. CSV parsing (`csv.DictReader`) has no existing analog in this extension but is stdlib with reference in RESEARCH.md. `q-tabs`/`q-tab-panels`/`q-file`/`q-date`/`q-popup-proxy` are standard Quasar v2 components (no existing usage in this extension, but documented in UI-SPEC.md with component structure). |

## Metadata

**Analog search scope:** `/home/exedev/giftcards/` (all .py, .vue, .js files), `/home/exedev/events/` (views_api.py, crud.py), `/home/exedev/lnbits/lnbits/decorators.py`, `/home/exedev/lnbits/lnbits/static/js/utils.js`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-30
