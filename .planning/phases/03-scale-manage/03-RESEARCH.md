# Phase 3: Scale & Manage - Research

**Researched:** 2026-06-30
**Domain:** LNBits extension — bulk gift card creation, REST API, issuer dashboard
**Confidence:** HIGH

## Summary

Phase 3 scales the single-card creation flow from Phases 1–2 into batch operations (same-amount form + variable-amount CSV upload with per-row validation), adds authenticated REST API endpoints for external automation (create, bulk create, list, detail with optional redemption link), and upgrades the issuer dashboard into a management console with status/search/date filters, multi-select bulk actions, card detail dialogs, editing, and deletion with sats reclaim. The entire phase builds on existing code: `create_gift_card()` in `services.py` is the atomic unit that bulk creation loops over; `get_cards_by_wallet()` in `crud.py` is the query the dashboard extends with filters; the `require_admin_key`/`require_invoice_key` decorators from `lnbits.decorators` are the auth pattern for the API; and the Quasar `q-table` in `index.vue` is the table that gains filters, multi-select, and detail/edit/delete dialogs.

No new runtime Python dependencies are needed. CSV parsing uses the stdlib `csv.DictReader` (already noted in the project stack). File upload uses FastAPI's `UploadFile` (already a core dependency via `python-multipart`). CSV export reuses the existing client-side `LNbits.utils.exportCSV` helper or a server-side `StreamingResponse`. The frontend is Vue 3 + Quasar with no build step — all new UI is additional `.vue` template sections and `.js` methods appended to the existing `index.vue`/`index.js`. One new migration (`m004`) is likely needed to add a `cancelled` status support column (the status column already accepts arbitrary strings, but an `updated_at` timestamp and/or an index on `status` + `created_at` will improve dashboard filter performance).

**Primary recommendation:** Implement in three vertical slices — (1) bulk creation (same-amount + CSV upload + validation), (2) REST API (bulk endpoint + invoice-key reads + `?include_link` flag + update/delete), (3) dashboard management (filters, multi-select, detail/edit/delete dialogs). Each slice is independently testable and ships a usable increment. Reuse `create_gift_card()` as the inner loop for all bulk paths; add `reclaim_sats_and_delete()` as a new service that wraps the existing `reclaim_card_sats()` + a hard `DELETE`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bulk same-amount creation | API / Backend | Database / Storage | Loop calls `create_gift_card()` (wallet debit + DB insert) server-side; frontend only sends count + amount + optional design |
| CSV upload + per-row validation | API / Backend | Browser / Client | Server parses + validates rows (stdlib `csv` + Pydantic row model); frontend displays validation table and summary, sends file via `UploadFile` |
| CSV validation table display | Browser / Client | — | Quasar `q-table` renders per-row green/red status from server-returned validation result; no cards created until all rows pass |
| REST API: create / bulk / list / detail / update / delete | API / Backend | Database / Storage | FastAPI routes with `require_admin_key` (writes) / `require_invoice_key` (reads); scoped to authenticated wallet |
| API redemption link opt-in (`?include_link=true`) | API / Backend | — | Server conditionally includes `redemption_url` (reconstructed from `raw_token`) only when flag is set; raw_token never exposed by default |
| Dashboard filters (status, search, date range) | Browser / Client | API / Backend | Filter controls in Quasar; either client-side filter on loaded list or server-side query params on `GET /cards` — recommend server-side for scalability |
| Multi-select bulk actions (send all, download CSV) | Browser / Client | API / Backend | Quasar `q-table` `selection="multiple"`; frontend collects selected IDs and calls existing per-card endpoints in a loop, or a new batch endpoint |
| Card detail dialog | Browser / Client | API / Backend | Expand row (existing pattern) + "View full details" button opens `q-dialog` with all fields including branded image preview |
| Card editing (metadata fields) | API / Backend | Database / Storage | New `PUT /cards/{id}` endpoint updates recipient_name, sender_name, message, recipient_email; amount change blocked with notice |
| Card deletion with sats reclaim | API / Backend | Database / Storage | New `DELETE /cards/{id}` endpoint: reclaim sats (for active cards) via existing `reclaim_card_sats()`, then hard `DELETE` row; redeemed cards rejected |
| CSV export (filtered) | Browser / Client | API / Backend | Reuse `LNbits.utils.exportCSV` client-side for loaded cards, or add server-side `GET /cards/csv` `StreamingResponse` for full filtered export |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Bulk Creation UI
- **D-01:** Separate "Bulk Create" button next to the existing "Create Gift Card" button. Opens a dedicated bulk dialog distinct from the single-card create dialog. Two entry points, two dialogs.
- **D-02:** Same-amount bulk uses a simple number input for quantity ("How many cards?"). Issuer types a number (e.g., 50). No slider, no dynamic recipient list. Cleanest UI for known quantities.
- **D-03:** After bulk creation: toast notification + dashboard refresh. The dashboard IS the results view. No dedicated results table in the dialog. The newly created cards appear in the filtered dashboard.
- **D-04:** "Download CSV" and "Send all emails" are available as dashboard actions (both global and per-selection — see D-12). Issuer exports links or triggers delivery from the dashboard after bulk creation.

#### CSV Upload Format
- **D-05:** Required columns: `recipient_name`, `amount_sats`. Optional columns: `recipient_email`, `nostr_npub`, `sender_name`, `message`. Email/npub are optional since not all cards need delivery. Matches BULK-02 spec.
- **D-06:** CSV design mode is a three-way choice in the bulk dialog:
  - "No design" — cards created with bare QR (Phase 1 style), no template/QR/text config
  - "One design for all rows" — issuer picks a design (template + QR + text styling) once in the bulk dialog, applied uniformly to every CSV row
  - "Per-row design columns" — CSV includes optional design columns (template_name, qr_x, qr_y, qr_size, text_x, text_y, font_size, font_color, etc.) for per-card customization
- **D-07:** CSV validation shows BOTH a per-row validation table (green check / red error per row) AND a summary ("X valid, Y errors"). Issuer must fix all errors before proceeding — no partial create. Matches BULK-03 exactly.
- **D-08:** Maximum 500 rows per CSV upload. Keeps the request responsive (500 card creations + funding in one batch). Planner should validate row count on upload and reject files exceeding the limit with a clear error.

#### REST API Design
- **D-09:** API mirrors existing card endpoints + adds a dedicated bulk endpoint. `POST /giftcards/api/v1/cards` (single create, existing), `POST /giftcards/api/v1/cards/bulk` (bulk create, new), `GET /giftcards/api/v1/cards` (list, existing), `GET /giftcards/api/v1/cards/{id}` (detail, existing). Minimal new code, consistent with existing patterns.
- **D-10:** Admin key required for all write operations (create, bulk create, delete, update). Invoice key accepted for all read operations (list, detail, status). Satisfies API-03 and fulfills D-11 deferred from Phase 1.
- **D-11:** Card status/detail API response includes: card_id, amount, status, recipient_name, sender_name, created_at, expires_at, redeemed_at, email_status. Redemption URL is NOT included by default. An optional `?include_link=true` query flag adds the redemption_url to the response. External systems opt in to receiving the link. This balances security (raw_token not exposed by default) with integration needs.

#### Dashboard Filters & Detail View
- **D-12:** Dashboard filters: status dropdown (created, active, redeemed, expired, cancelled) + free-text search (searches recipient name, sender name, card ID) + date range picker (created_at between X and Y). Covers DASH-02 for common filter use cases.
- **D-13:** Card detail view is a hybrid: expand row in the q-table for quick view (summary + key actions), plus a "View full details" button in the expanded row that opens a detail dialog with everything including branded image preview. No separate route/page.
- **D-14:** Bulk dashboard actions: BOTH global buttons above the table ("Send all (filtered)", "Download CSV (filtered)") AND multi-select checkboxes on rows for targeted actions on specific cards. Global buttons apply to all filtered cards; multi-select applies to checked cards only.

#### Card Editing & Deletion
- **D-15:** Issuer can edit all card metadata fields: recipient_name, sender_name, message, recipient_email, and amount. However, amount changes require cancel + recreate — the issuer cancels the card (reclaims sats) and creates a new one with the desired amount. The edit dialog for amount shows a notice: "To change the amount, cancel this card and create a new one." All other fields are directly editable.
- **D-16:** Card deletion is allowed only for non-redeemed cards (status: created, active, expired). Redeemed cards cannot be deleted. For active cards, sats are reclaimed to the issuer wallet first, then the record is deleted. For expired cards, sats are already reclaimed (by the expiry task), so just delete the record. Hard delete, not soft delete — no audit trail retained (AUDT-02 soft delete is v2).
- **D-17:** Delete requires a confirmation dialog ("Are you sure? This will reclaim X sats to your wallet and permanently delete this card.").

### Claude's Discretion
- CSV column naming convention (snake_case vs camelCase) — must be documented in the bulk dialog with a downloadable template
- Exact design column names in per-row CSV mode — must map to existing DesignConfig fields
- CSV parsing library (Python stdlib `csv` module is sufficient, no new dependency needed)
- Bulk creation transaction strategy (all-or-nothing vs batch-with-progress) — must handle partial failures gracefully
- API response format for bulk creation (array of card objects vs summary with card IDs)
- Date range picker UI component (Quasar QDate or similar)
- Multi-select checkbox implementation in Quasar q-table
- Detail dialog layout and component structure
- Edit dialog form structure and validation
- Whether bulk "Send all emails" runs synchronously or as a background task (consider SMTP latency for 500 emails)

### Deferred Ideas (OUT OF SCOPE)
- **Nostr delivery (DELV-03)** — Still deferred from Phase 2. LNBits core has `send_nostr_dm()` infrastructure. Future phase.
- **Audit log per card (AUDT-01)** — v2. Phase 3 does hard delete with no audit trail. AUDT-02 soft delete/cancel with audit trail is v2.
- **Printable PDF / cut sheet (PRNT-01)** — v2. Phase 3 focuses on CSV export of card data, not print-optimized layouts.
- **SMS delivery (PRNT-02)** — v2. Pluggable provider model.
- **Background job for bulk email sending** — If "Send all emails" for 500 cards is too slow synchronously, a background task with progress tracking could be added. For now, planner's discretion on sync vs async.
- **Webhook notifications for card status changes** — External systems polling the API is sufficient for v1. Webhooks could be a future enhancement.
- **Rate limiting on API endpoints** — Phase 3 adds the API surface but rate limiting on API calls is deferred (Phase 1 D-06 deferred rate limiting to Phase 6; API rate limiting follows the same pattern).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BULK-01 | Issuer can create multiple gift cards with the same sats amount from a single form. | Bulk same-amount creation: new `BulkCreateRequest` model (amount + count + optional design) → `POST /cards/bulk` endpoint → loop over `create_gift_card()`. Frontend: "Bulk Create" button + dialog with quantity number input (D-01, D-02). |
| BULK-02 | Issuer can upload a CSV file with columns for recipient name, sats amount, email address, and nostr npub to create gift cards in bulk. | CSV upload: `UploadFile` endpoint parses with `csv.DictReader`, validates each row against a `CSVRow` Pydantic model. Required cols: `recipient_name`, `amount_sats`; optional: `recipient_email`, `nostr_npub`, `sender_name`, `message` (D-05). 500-row max (D-08). |
| BULK-03 | Bulk CSV creation validates each row and reports per-row errors before creating any cards. | Two-phase CSV flow: (1) upload → server returns per-row validation table (green/red) + summary; (2) issuer fixes errors, re-uploads; only when all rows pass does the "Create" button fire the actual bulk create. No partial create (D-07). |
| BULK-04 | Bulk creation generates a unique redemption link and optional email/nostr delivery for each card. | `create_gift_card()` already generates unique `raw_token` + `redemption_url` per card. Bulk loop calls it N times. Email delivery is a separate post-creation dashboard action ("Send all") — matches D-04 and Phase 2 D-24 (create first, deliver later). Nostr deferred (DELV-03). |
| API-01 | External systems can create gift cards via an authenticated REST API endpoint. | Existing `POST /giftcards/api/v1/cards` (single create, `require_admin_key`) already satisfies this. New `POST /giftcards/api/v1/cards/bulk` adds bulk create via API (D-09). |
| API-02 | External systems can retrieve gift card status and details via an authenticated REST API endpoint. | Existing `GET /cards` (list) + `GET /cards/{id}` (detail) — switch to accept `require_invoice_key` for reads (D-10). Detail response includes status, dates, email_status; `?include_link=true` adds `redemption_url` (D-11). |
| API-03 | All issuer-facing API endpoints require an LNBits admin or invoice key and are scoped to the authenticated wallet. | `require_admin_key` for writes (create, bulk, update, delete); `require_invoice_key` for reads (list, detail). Wallet ID derived from key, never from request body. Events extension uses this exact mixed-auth pattern (views_api.py §155, §168). |
| DASH-01 | Issuer can view a list of all gift cards they have created. | Existing `GET /cards` + `get_cards_by_wallet()` + Quasar `q-table` in `index.vue` already satisfy this. Phase 3 enhances with filters and multi-select. |
| DASH-02 | Issuer can filter gift cards by status (created, active, redeemed, expired, cancelled). | New filter controls: status dropdown, free-text search, date range picker (D-12). Server-side query params on `GET /cards` (recommended) or client-side filter. New `get_cards_by_wallet_filtered()` CRUD function. |
| DASH-03 | Issuer can view gift card details including status, creation date, expiration date, and redemption date. | Hybrid detail view: expand row (existing) + "View full details" `q-dialog` with all fields + branded image preview (D-13). Detail API endpoint returns full card data. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Extracted from `.claude/CLAUDE.md` (GSD-managed, sourced from PROJECT.md + research/STACK.md):

- **Tech stack:** Must be built as an LNBits extension, matching the runtime version and conventions of the target LNBits installation (LNBits v1.5.4, Python 3.10–3.12, FastAPI ~0.116.1, Pydantic **v1** ~1.10.26, SQLAlchemy ~1.4.54).
- **Security:** Redemption links/tokens must be unguessable and single-use. Store SHA-256 hash of token; `raw_token` stored in DB (post-session decision) but NOT exposed in public/list API responses by default. `?include_link=true` is the explicit opt-in.
- **Compatibility:** Must work alongside existing LNBits wallet and account system without breaking core flows.
- **Performance:** Bulk creation of hundreds of cards should be responsive; image generation should not block the request thread. Use `asyncio.to_thread()` for CPU-bound work; `asyncio.create_task` for fire-and-forget.
- **Privacy:** Recipient email/nostr npub is stored only as needed for delivery and should not be exposed publicly.
- **Forbidden:** Pydantic v2, Flask/Quart/Django, Celery/Redis, pandas, `uuid4`/short hashes as redemption secrets, client-side QR generation, plaintext token storage in public responses, new runtime dependencies not in LNBits core.
- **CSV parsing:** Use stdlib `csv.DictReader` — no `pandas` (heavyweight, not in core, violates dependency policy).
- **Email:** Reuse LNBits core SMTP settings (`settings.lnbits_email_notifications_*`); custom `MIMEMultipart` for attachments (core `send_email_notification` does not support attachments).
- **DB:** All tables namespaced `ext_giftcards.*`; use `lnbits.db.Database("ext_giftcards")`; migrations are sequential `mNNN_name(db)` functions; `db.timestamp_placeholder()` for cross-DB timestamp params.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | ~0.116.1 | Extension HTTP API / router (APIRouter) | LNBits core is FastAPI; extensions are APIRouter instances [VERIFIED: codebase — views_api.py] |
| Pydantic | ~1.10.26 (v1) | Request/response models + validation | LNBits 1.5.x uses Pydantic v1; v2 is incompatible [VERIFIED: codebase — models.py uses `@validator`] |
| `lnbits.db.Database` | core | DB access (SQLite/PostgreSQL) | Abstracts both drivers; all tables namespaced `ext_giftcards.*` [VERIFIED: codebase — crud.py] |
| `lnbits.decorators` | core | Auth: `require_admin_key` / `require_invoice_key` | Wallet-scoped key auth; events extension uses both [VERIFIED: codebase — decorators.py §204, events/views_api.py §155/§168] |
| `csv` (stdlib) | builtin | CSV parsing for bulk upload | No new dependency; `csv.DictReader` sufficient for 500 rows [VERIFIED: codebase — STACK.md] |
| `fastapi.UploadFile` | ~0.116.1 | Multipart file upload for CSV | Already available via `python-multipart` core dep [VERIFIED: codebase — core/services/assets.py uses UploadFile] |
| Vue 3 + Quasar | bundled in LNBits core | Issuer dashboard UI | `.vue` + `.js` files, no build step [VERIFIED: codebase — static/js/index.vue] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.to_thread` | stdlib | Offload CSV parsing / SMTP to thread | CSV parse for 500 rows is light, but bulk email send (500 × SMTP) must be offloaded |
| `asyncio.create_task` | stdlib | Fire-and-forget background email send | "Send all emails" for many cards — avoid blocking the dashboard response |
| `StreamingResponse` | FastAPI ~0.116.1 | CSV export file download | Server-side `GET /cards/csv` returns streaming CSV; already used for PNG images [VERIFIED: codebase — views_api.py §226] |
| `lnbits.core.services.payments.update_wallet_balance` | core | Sats reclaim on delete | Credit issuer wallet back when deleting active cards [VERIFIED: codebase — services.py §109, §177] |
| `LNbits.utils.exportCSV` | core JS | Client-side CSV export | Existing helper in `lnbits/static/js/utils.js` §273; used by events extension [VERIFIED: codebase] |
| Quasar `q-table` selection | bundled | Multi-select checkboxes | `selection="multiple"` prop + `v-model:selected` for checked rows [ASSUMED — standard Quasar v2 feature] |
| Quasar `q-date` | bundled | Date range picker | Quasar's date picker component for created_at range filter [ASSUMED — standard Quasar v2 feature] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Server-side CSV parsing (`csv.DictReader`) | Client-side JS parsing (PapaParse) | Server-side is more secure (validation before any DB write), no new JS dependency, matches BULK-03 "validate before create". Client-side would add a dependency and bypass server authority. |
| Server-side filtered query (`GET /cards?status=...&search=...`) | Client-side filter on full loaded list | Server-side scales to thousands of cards; client-side is simpler but breaks at volume. Recommend server-side with query params. |
| Server-side CSV export (`StreamingResponse`) | Client-side `LNbits.utils.exportCSV` | Server-side handles full filtered set (even > page size); client-side only exports currently loaded rows. Use server-side for "Download CSV (filtered)" global action; client-side is the existing "Export CSV" button. |
| Loop over `create_gift_card()` for bulk | Single batched DB insert + batch wallet debit | Loop reuses tested single-card logic (token gen, funding, design config). Batched insert is faster but duplicates logic and risks inconsistency. For 500 cards, loop is acceptable (each is ~2 DB ops + 1 balance update). [VERIFIED: codebase — create_gift_card is the atomic unit] |

**Installation:**
```bash
# No new packages needed. All dependencies are in LNBits core.
# The extension only declares "lnbits>1" as its dependency.
```

**Version verification:** No new packages to verify — all are LNBits core dependencies already confirmed in prior research (STACK.md). Stdlib modules (`csv`, `asyncio`) require no version check.

## Package Legitimacy Audit

> This phase installs **no external packages**. All functionality uses LNBits core dependencies or Python stdlib.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | No new packages |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*No packages discovered via WebSearch or training data — all dependencies are pre-existing LNBits core packages verified in prior research.*

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (Issuer UI)                          │
│  index.vue / index.js                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Bulk Create  │  │ Dashboard    │  │ Detail/Edit/Delete       │  │
│  │ Dialog       │  │ Filters +    │  │ Dialogs                  │  │
│  │ (same-amt +  │  │ Multi-select │  │                          │  │
│  │  CSV upload) │  │ q-table      │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
└─────────┼─────────────────┼─────────────────────┼──────────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI APIRouter (/giftcards/api/v1)             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  POST /cards          (create, admin key)     [existing]     │   │
│  │  POST /cards/bulk     (bulk create, admin)    [NEW]          │   │
│  │  POST /cards/csv      (CSV upload+validate, admin) [NEW]     │   │
│  │  GET  /cards          (list, admin OR invoice) [modified]    │   │
│  │  GET  /cards/{id}     (detail, admin OR invoice) [modified]  │   │
│  │  PUT  /cards/{id}     (update, admin)        [NEW]           │   │
│  │  DELETE /cards/{id}   (delete+reclaim, admin) [NEW]          │   │
│  │  GET  /cards/csv      (export filtered, admin) [NEW]         │   │
│  └────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       services.py (Business Logic)                  │
│  ┌────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ create_gift_   │  │ parse_csv()      │  │ reclaim_sats_      │  │
│  │ card()         │  │ validate_csv_   │  │ and_delete()       │  │
│  │ [existing]     │  │ rows()   [NEW]  │  │ [NEW]              │  │
│  │ (inner loop)   │  └──────────────────┘  └────────────────────┘  │
│  └────────────────┘                                                 │
│  ┌────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ bulk_create_   │  │ export_cards_    │  │ send_gift_card_    │  │
│  │ with_funding() │  │ csv()    [NEW]   │  │ email() [existing] │  │
│  │ [NEW]          │  └──────────────────┘  └────────────────────┘  │
│  └────────────────┘                                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       crud.py (Pure DB I/O)                         │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │ get_cards_by_    │  │ get_cards_by_wallet_ │  │ delete_card  │  │
│  │ wallet() [exist] │  │ filtered()   [NEW]   │  │ ()    [NEW]  │  │
│  └──────────────────┘  └──────────────────────┘  └──────────────┘  │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │ create_card()    │  │ update_card_fields() │  │ get_card()   │  │
│  │ [existing]       │  │ ()          [NEW]    │  │ [existing]   │  │
│  └──────────────────┘  └──────────────────────┘  └──────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              lnbits.db.Database("ext_giftcards")                    │
│  giftcards.cards (m001–m003) + m004 (updated_at, indexes)          │
│  giftcards.magic_links (m003)                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Data flow — CSV bulk creation (primary use case):**
1. Issuer selects CSV file in bulk dialog → frontend sends file to `POST /cards/csv` (admin key)
2. Server parses with `csv.DictReader` → validates each row against `CSVRow` Pydantic model → returns `{valid: [...], errors: [...], summary: {valid_count, error_count}}` **without creating any cards**
3. Frontend renders per-row validation table (green/red) + summary; "Create" button disabled if any errors
4. Issuer fixes errors → re-uploads → all rows pass → clicks "Bulk Create"
5. Frontend sends validated rows to `POST /cards/bulk` (admin key) → server loops `create_gift_card()` per row (token gen + DB insert + wallet debit)
6. Server returns summary `{created: N, card_ids: [...], failed: [...]}` → frontend toast + dashboard refresh
7. Newly created cards appear in filtered dashboard; issuer uses "Send all" / "Download CSV" actions

### Recommended Project Structure

```
giftcards/                          # (repo root = extension package)
├── __init__.py                     # Router registration [modify: no change needed]
├── views_api.py                    # API endpoints [modify: add bulk, csv, update, delete, export; switch reads to invoice key]
├── services.py                     # Business logic [modify: add bulk_create, parse_csv, validate_csv_rows, reclaim_sats_and_delete, export_cards_csv]
├── crud.py                         # DB I/O [modify: add get_cards_by_wallet_filtered, update_card_fields, delete_card]
├── models.py                       # Pydantic models [modify: add BulkCreateRequest, CSVRow, CSVValidationResult, UpdateCardRequest, CardDetailResponse]
├── migrations.py                   # DB migrations [modify: add m004 — updated_at column + indexes]
├── tasks.py                        # Background tasks [no change]
├── views.py                        # Generic routes [no change]
├── config.json                     # Extension config [no change]
├── static/
│   └── js/
│       ├── index.vue               # Issuer UI [modify: add bulk dialog, filters, multi-select, detail/edit/delete dialogs]
│       ├── index.js                # Issuer JS [modify: add bulk, filter, edit, delete, multi-select logic]
│       ├── redeem.vue              # Public redemption [no change]
│       ├── redeem.js               # Public redemption [no change]
│       ├── claim.vue               # Claim page [no change]
│       └── claim.js                # Claim page [no change]
└── tests/
    ├── test_bulk_creation.py       # [NEW] bulk same-amount + CSV validation tests
    ├── test_api.py                 # [NEW] REST API endpoint tests (invoice key reads, include_link, update, delete)
    ├── test_dashboard.py           # [NEW] filtered query tests
    └── (existing test files)       # [modify: update for new model fields if needed]
```

### Pattern 1: Bulk Creation via Inner-Loop Reuse
**What:** Bulk creation loops over the existing single-card `create_gift_card()` rather than writing a separate batched insert.
**When to use:** All bulk creation paths (same-amount form, CSV upload, API bulk endpoint).
**Why:** `create_gift_card()` already handles token generation, wallet debit, design config serialization, and DB insert. Reusing it avoids duplicating security-critical logic (token gen, wallet scoping). For 500 cards, the loop is ~1000 DB ops + 500 balance updates — acceptable in a single request with proper error handling.
**Example:**
```python
# Source: codebase pattern — services.py create_gift_card() §39
async def bulk_create_with_funding(
    rows: list[CreateGiftCard],  # validated rows
    issuer_wallet_id: str,
    user_id: str,
    base_url: str,
) -> BulkCreateResult:
    created = []
    failed = []
    for row in rows:
        try:
            response = await create_gift_card(
                data=row,
                issuer_wallet_id=issuer_wallet_id,
                user_id=user_id,
                base_url=base_url,
            )
            created.append(response)
        except Exception as exc:
            logger.error(f"Bulk create failed for row: {exc}")
            failed.append({"row": row, "error": str(exc)})
            # NOTE: per D-07, CSV validation ensures all rows pass BEFORE
            # creation. Same-amount bulk has no per-row validation risk.
            # Partial failure handling is a safety net, not the primary path.
    return BulkCreateResult(created=created, failed=failed)
```

### Pattern 2: Two-Phase CSV Validation (No Partial Create)
**What:** CSV upload is a separate endpoint that ONLY validates — it does not create cards. A second endpoint creates cards only after all rows pass validation.
**When to use:** CSV bulk upload (BULK-02, BULK-03).
**Why:** BULK-03 requires "validates each row and reports per-row errors before creating any cards." A single endpoint that validates-then-creates would either create partial cards on error (violating D-07) or require a transaction rollback across 500 wallet debits (complex). Two phases cleanly separate validation from creation.
**Example:**
```python
# Source: codebase pattern — Pydantic v1 validators in models.py
class CSVRow(BaseModel):
    recipient_name: str
    amount_sats: int = Field(..., gt=0)
    recipient_email: Optional[str] = None
    nostr_npub: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    # Per-row design columns (optional, D-06 "per-row design" mode)
    template_name: Optional[str] = None
    qr_x_frac: Optional[float] = None
    # ... maps to DesignConfig fields

    @validator("recipient_email")
    def _normalize_email(cls, v):
        return _normalize_email(v)

    @validator("amount_sats")
    def _positive_amount(cls, v):
        if v <= 0:
            raise ValueError("amount_sats must be > 0")
        return v

# Endpoint 1: validate only
@giftcards_api_router.post("/csv")
async def api_validate_csv(
    file: UploadFile,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> CSVValidationResult:
    content = await file.read()
    rows = parse_csv(content)  # csv.DictReader
    if len(rows) > 500:
        raise HTTPException(422, "CSV exceeds 500 row maximum")
    valid, errors = validate_csv_rows(rows)
    return CSVValidationResult(
        valid_count=len(valid),
        error_count=len(errors),
        valid_rows=valid,
        errors=errors,  # [{row_num, field, message}]
    )

# Endpoint 2: create (only called after validation passes)
@giftcards_api_router.post("/bulk")
async def api_bulk_create(
    data: BulkCreateRequest,  # contains validated rows or count+amount
    wallet: WalletTypeInfo = Depends(require_admin_key),
    request: Request,
) -> BulkCreateResult:
    ...
```

### Pattern 3: Mixed Auth — Admin Writes, Invoice Reads
**What:** Write endpoints use `require_admin_key`; read endpoints use `require_invoice_key`. Both derive wallet scope from the key, never from the request body.
**When to use:** All Phase 3 API endpoints (D-09, D-10).
**Why:** API-03 requires admin OR invoice key scoping. The events extension uses this exact pattern (`require_invoice_key` for list at §155, `require_admin_key` for create at §168). Invoice key is read-only (cannot spend); admin key can create/delete.
**Example:**
```python
# Source: codebase — events/views_api.py §155, §168; decorators.py §204
from lnbits.decorators import require_admin_key, require_invoice_key

# Read — invoice key accepted (D-10)
@giftcards_api_router.get("")
async def api_get_cards(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> list[GiftCardSummary]:
    cards = await get_cards_by_wallet(wallet.wallet.id)
    return cards

# Write — admin key required (D-10)
@giftcards_api_router.delete("/{card_id}")
async def api_delete_card(
    card_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    card = await get_card(card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    if card.wallet != wallet.wallet.id:
        raise HTTPException(403, "Card does not belong to this wallet")
    if card.status == "redeemed":
        raise HTTPException(409, "Redeemed cards cannot be deleted")
    # Reclaim sats for active cards, then hard delete
    await reclaim_sats_and_delete(card)
    return {"status": "deleted"}
```

### Pattern 4: Server-Side Filtered Query
**What:** Dashboard filters (status, search, date range) are query parameters on `GET /cards`, filtered server-side in the CRUD query.
**When to use:** Dashboard filter (DASH-02, D-12).
**Why:** Client-side filtering breaks at scale (hundreds/thousands of cards). Server-side filtering with parameterized SQL is secure and scalable. The existing `get_cards_by_wallet()` is extended with optional WHERE clauses.
**Example:**
```python
# Source: codebase pattern — crud.py get_cards_by_wallet() §35
async def get_cards_by_wallet_filtered(
    wallet_id: str,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> list[GiftCardSummary]:
    query = "SELECT id, amount, status, recipient_name, sender_name, message, expires_at, created_at, redeemed_at, expired_at, redemption_url, recipient_email, email_status FROM giftcards.cards WHERE wallet = :wallet"
    values = {"wallet": wallet_id}
    if status:
        query += " AND status = :status"
        values["status"] = status
    if search:
        query += " AND (recipient_name ILIKE :search OR sender_name ILIKE :search OR id ILIKE :search)"
        values["search"] = f"%{search}%"
    if date_from:
        query += f" AND created_at >= {db.timestamp_placeholder('date_from')}"
        values["date_from"] = date_from.timestamp()
    if date_to:
        query += f" AND created_at <= {db.timestamp_placeholder('date_to')}"
        values["date_to"] = date_to.timestamp()
    query += " ORDER BY created_at DESC"
    return await db.fetchall(query, values, GiftCardSummary)
```
**Note:** `ILIKE` works in PostgreSQL; SQLite is case-insensitive for `LIKE` by default. For cross-DB compatibility, use `LOWER(col) LIKE LOWER(:search)` or check `db.type` to choose the operator. The existing codebase uses plain parameterized SQL (no ORM), so this pattern is consistent. [VERIFIED: codebase — crud.py uses raw SQL with `:param` placeholders]

### Pattern 5: Sats Reclaim + Hard Delete
**What:** Deleting an active card reclaims sats to the issuer wallet first (via existing `reclaim_card_sats()`), then hard-deletes the DB row. Expired cards skip reclaim (sats already reclaimed by expiry task). Redeemed cards are rejected.
**When to use:** Card deletion (D-16).
**Why:** D-16 specifies hard delete with sats reclaim for active cards. The existing `reclaim_card_sats()` (services.py §165) already credits the issuer wallet. Wrapping it with a `DELETE` in a new `reclaim_sats_and_delete()` service keeps the logic in one place.
**Example:**
```python
# Source: codebase — services.py reclaim_card_sats() §165
async def reclaim_sats_and_delete(card: GiftCard) -> None:
    """Reclaim sats (if active) and hard-delete the card record."""
    if card.status == "active":
        await reclaim_card_sats(card)  # credits issuer wallet
    # Expired cards: sats already reclaimed by expiry task — skip
    # Redeemed cards: caller must reject before reaching here
    await delete_card(card.id)  # new crud function: DELETE FROM giftcards.cards WHERE id = :id
```

### Anti-Patterns to Avoid

- **Do NOT create a separate bulk DB insert that bypasses `create_gift_card()`.** Duplicating token generation, wallet debit, and design config serialization introduces security bugs. Reuse the single-card function as the inner loop. [VERIFIED: codebase — create_gift_card is the tested atomic unit]
- **Do NOT validate CSV and create cards in the same request.** BULK-03 requires validation BEFORE creation. A combined endpoint either creates partial cards on error (violates D-07) or needs a complex transaction. Use two-phase: validate endpoint → create endpoint.
- **Do NOT derive wallet_id from the request body.** Always derive from the API key via `require_admin_key`/`require_invoice_key`. The existing codebase does this correctly (views_api.py §59, §77). [VERIFIED: codebase]
- **Do NOT expose `raw_token` in API responses by default.** D-11 requires `?include_link=true` opt-in. The existing `GiftCardSummary` model includes `redemption_url` (which contains the raw_token in the path) — for the API detail endpoint, conditionally include it based on the query flag. For the dashboard (admin-key authenticated), `redemption_url` is already shown. [VERIFIED: codebase — models.py GiftCardSummary §197]
- **Do NOT use `pandas` for CSV parsing.** It is not in LNBits core and violates the dependency policy. Use stdlib `csv.DictReader`. [VERIFIED: STACK.md]
- **Do NOT block the event loop for bulk email sending.** 500 SMTP sends synchronously could take minutes. Use `asyncio.create_task` for fire-and-forget, or `asyncio.to_thread` for sequential-but-offloaded. Show a progress indicator in the UI. [VERIFIED: codebase — services.py uses asyncio.to_thread for SMTP §498]
- **Do NOT use Pydantic v2 syntax.** LNBits 1.5.x uses Pydantic v1. Use `@validator` not `@field_validator`, `Field(...)` not `Field(...)`, `BaseModel.dict()` not `model_dump()`. [VERIFIED: codebase — models.py uses v1 syntax]
- **Do NOT use `ILIKE` without checking DB type.** `ILIKE` is PostgreSQL-specific. SQLite needs `LIKE` (case-insensitive by default) or `LOWER()`. Use `db.type` check or `LOWER(col) LIKE LOWER(:search)` for cross-DB compatibility. [ASSUMED — standard SQL compatibility knowledge]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV parsing | Custom line-by-line parser | `csv.DictReader` (stdlib) | Handles quoted fields, escaped quotes, varied line endings, BOM stripping — all edge cases that custom parsers miss |
| CSV validation | Manual field-by-field checks | Pydantic v1 `CSVRow` model with `@validator` | Type coercion, error messages, email normalization — all already implemented in existing models pattern |
| CSV export (client-side) | Custom CSV string builder | `LNbits.utils.exportCSV(columns, data)` | Already in LNBits core JS (utils.js §273); handles quoting, escaping, formatting |
| Auth + wallet scoping | Custom API key parsing | `require_admin_key` / `require_invoice_key` decorators | Already handle key validation, wallet lookup, user scoping — events extension uses both |
| Wallet balance operations | Direct SQL on balances table | `update_wallet_balance(wallet, amount)` | Already used in create_gift_card and reclaim_card_sats; handles balance correctly in sats (not millisats) |
| Sats reclaim on delete | New balance credit logic | `reclaim_card_sats()` (existing) | Already credits issuer wallet correctly; handles missing wallet gracefully |
| File upload parsing | Custom multipart parser | `fastapi.UploadFile` | Already used by LNBits core asset upload; `python-multipart` is a core dependency |
| Date range picker UI | Custom date inputs | Quasar `q-date` component | Bundled in LNBits Quasar; standard component with popup, range support |

**Key insight:** Every Phase 3 capability has a building block already in the codebase or LNBits core. The phase is primarily about composing existing primitives (create_gift_card, reclaim_card_sats, require_invoice_key, q-table, csv.DictReader) into new endpoints and UI flows — not inventing new infrastructure.

## Common Pitfalls

### Pitfall 1: CSV Validation Bypass via Combined Endpoint
**What goes wrong:** A single CSV endpoint that validates-then-creates will create partial cards if an error occurs mid-batch, violating BULK-03/D-07 ("no partial create").
**Why it happens:** It seems simpler to do everything in one request. But 500 wallet debits + DB inserts cannot be trivially rolled back, and a failure at row 250 leaves 250 cards created.
**How to avoid:** Two-phase flow: `POST /cards/csv` (validate only, returns per-row results) → frontend shows validation table → issuer fixes → `POST /cards/bulk` (create only, all rows pre-validated). The create endpoint can still fail individually (network, wallet balance), but validation errors are caught before any creation.
**Warning signs:** Any endpoint that both parses CSV and calls `create_gift_card()` in the same function.

### Pitfall 2: Wallet Balance Exhaustion During Bulk Create
**What goes wrong:** Creating 500 cards at 1000 sats each requires 500,000 sats. If the issuer's wallet balance is insufficient, `update_wallet_balance` will fail partway through, leaving some cards created and funded, others not created.
**Why it happens:** The bulk create loop debits the wallet per-card. No pre-check of total required sats vs. available balance.
**How to avoid:** Pre-check: `total_required = count * amount` (same-amount) or `sum(row.amount_sats for row in rows)` (CSV). Compare against wallet balance BEFORE starting the loop. If insufficient, return a 422 error with the shortfall. For the CSV path, this check happens in the validate endpoint (return a balance warning in the validation result).
**Warning signs:** No balance pre-check before bulk create; bulk create endpoint that starts the loop without verifying total sats.

### Pitfall 3: SQLite ILIKE Incompatibility
**What goes wrong:** Using `ILIKE` for case-insensitive search works in PostgreSQL but fails in SQLite (which doesn't support `ILIKE`).
**Why it happens:** LNBits supports both SQLite (dev) and PostgreSQL (prod). The search query must work on both.
**How to avoid:** Use `LOWER(col) LIKE LOWER(:search)` for cross-DB case-insensitive search, or check `db.type` and use `ILIKE` for PostgreSQL / `LIKE` for SQLite. The existing codebase uses raw SQL (no ORM), so this must be handled in the query string.
**Warning signs:** Search filter that only works on one DB type; tests that only run against SQLite.

### Pitfall 4: raw_token Leakage in API Responses
**What goes wrong:** The existing `GiftCardSummary` model includes `redemption_url` (which embeds the raw_token in the path). If the API detail endpoint returns this by default, external systems get redemption links without opting in — violating D-11.
**Why it happens:** The dashboard (admin-key) already shows `redemption_url` — it's in the model. The API read endpoint (invoice-key) must NOT include it by default.
**How to avoid:** Create a separate `CardDetailResponse` model for the API that omits `redemption_url` by default. Only add it when `?include_link=true` is passed. The dashboard continues using `GiftCardSummary` (admin-key, full trust). Alternatively, use a response model factory that conditionally includes the field.
**Warning signs:** API detail endpoint returning `redemption_url` without the `include_link` flag; same model used for both admin dashboard and external API.

### Pitfall 5: Blocking Event Loop with Bulk Email
**What goes wrong:** "Send all emails" for 500 cards calls `send_gift_card_email()` 500 times. Each does an SMTP send (offloaded to thread), but the loop itself blocks the async event loop between sends if not properly awaited/gathered.
**Why it happens:** Sequential `await send_gift_card_email()` in a loop is correct but slow (500 × ~1s SMTP = ~8 minutes). The dashboard UI freezes waiting for the response.
**How to avoid:** Use `asyncio.create_task` to fire-and-forget the batch, return immediately with a "sending started" response, and let the frontend poll card `email_status` for progress. Or use `asyncio.gather` with a concurrency limiter (e.g., `asyncio.Semaphore(10)`) to parallelize while bounding SMTP connections. Show a progress indicator in the UI. This is Claude's discretion per CONTEXT.md.
**Warning signs:** "Send all" button that takes minutes to return a response; no progress feedback; SMTP connection errors from too many concurrent connections.

### Pitfall 6: Missing Wallet Ownership Check on Update/Delete
**What goes wrong:** An issuer with a valid admin key for wallet A could update or delete a card belonging to wallet B by guessing the card ID.
**Why it happens:** The card ID is in the URL path, not derived from the key. If the endpoint doesn't verify `card.wallet == wallet.wallet.id`, it's a cross-wallet access control bug.
**How to avoid:** Every update/delete endpoint must fetch the card, verify `card.wallet == wallet.wallet.id`, and return 403 if mismatched. The existing deliver endpoint already does this (views_api.py §315). [VERIFIED: codebase — views_api.py §315 `if card.wallet != wallet.wallet.id`]
**Warning signs:** Update/delete endpoint that doesn't check `card.wallet`; tests that don't cover cross-wallet rejection.

### Pitfall 7: Quasar q-table `:model-value` vs `:value` Binding
**What goes wrong:** New Quasar form components in dialogs use `:value` instead of `:model-value` for one-way binding, causing inputs to not update.
**Why it happens:** Quasar v2 changed the binding prop name. This was already a post-session fix in Phase 1 (STATE.md).
**How to avoid:** All `q-input` components must use `:model-value` (not `:value`) for one-way binding. For two-way binding, use `v-model`. [VERIFIED: STATE.md post-session note; codebase — index.vue uses `:model-value`]
**Warning signs:** `q-input` with `:value` prop; inputs that don't reflect state changes.

## Code Examples

### BulkCreateRequest Model (Pydantic v1)
```python
# Source: codebase pattern — models.py CreateGiftCard §119, DesignConfig §21
class BulkCreateRequest(BaseModel):
    """Same-amount bulk creation request."""
    count: int = Field(..., gt=0, le=500, description="Number of cards to create")
    amount: int = Field(..., gt=0, description="Amount in sats per card")
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None

    @validator("count")
    def _max_count(cls, v):
        if v > 500:
            raise ValueError("Maximum 500 cards per bulk create")
        return v

    @validator("amount")
    def _positive_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @validator("recipient_email")
    def _normalize_email(cls, v):
        return _normalize_email(v)

    @validator("expires_at", pre=True)
    def parse_expires_at(cls, v):
        # Reuse the same date-parsing logic from CreateGiftCard
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

### CSV Row Validation Model
```python
# Source: codebase pattern — models.py validators, _normalize_email §14
class CSVRow(BaseModel):
    """One row from a CSV upload, validated before any card creation."""
    row_num: int  # 1-based line number for error reporting
    recipient_name: str
    amount_sats: int = Field(..., gt=0)
    recipient_email: Optional[str] = None
    nostr_npub: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    # Per-row design columns (D-06 "per-row design" mode)
    template_name: Optional[str] = None
    qr_x_frac: Optional[float] = None
    qr_y_frac: Optional[float] = None
    qr_size: Optional[int] = None
    text_x_frac: Optional[float] = None
    text_y_frac: Optional[float] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    text_align: Optional[str] = None

    @validator("recipient_email")
    def _normalize_email(cls, v):
        return _normalize_email(v)

    @validator("amount_sats")
    def _positive(cls, v):
        if v <= 0:
            raise ValueError("amount_sats must be > 0")
        return v

class CSVValidationError(BaseModel):
    row_num: int
    field: str
    message: str

class CSVValidationResult(BaseModel):
    valid_count: int
    error_count: int
    valid_rows: list[CSVRow]
    errors: list[CSVValidationError]
```

### CSV Parsing + Validation (stdlib csv)
```python
# Source: STACK.md — csv.DictReader; codebase pattern
import csv
import io

def parse_csv(content: bytes) -> list[dict]:
    """Parse CSV bytes into a list of dicts using csv.DictReader."""
    # Handle BOM and decode
    text = content.decode("utf-8-sig")  # strips BOM if present
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader, start=2):  # row 1 is header
        row["row_num"] = i
        rows.append(row)
    return rows

def validate_csv_rows(rows: list[dict]) -> tuple[list[CSVRow], list[CSVValidationError]]:
    """Validate each row against CSVRow model. Returns (valid, errors)."""
    valid = []
    errors = []
    for row in rows:
        try:
            # Strip None/empty strings for optional fields
            cleaned = {k: (v if v != "" else None) for k, v in row.items()}
            csv_row = CSVRow(**cleaned)
            valid.append(csv_row)
        except Exception as exc:
            # Pydantic v1 ValidationError contains field-specific errors
            for err in exc.errors():
                field = ".".join(str(x) for x in err["loc"])
                errors.append(CSVValidationError(
                    row_num=row.get("row_num", 0),
                    field=field,
                    message=err["msg"],
                ))
    return valid, errors
```

### Update Card Endpoint
```python
# Source: codebase pattern — views_api.py §296 (deliver endpoint), §315 (ownership check)
class UpdateCardRequest(BaseModel):
    """Editable card fields. Amount is NOT included (D-15)."""
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    recipient_email: Optional[str] = None

    @validator("recipient_email")
    def _normalize_email(cls, v):
        return _normalize_email(v)

@giftcards_api_router.put("/{card_id}")
async def api_update_card(
    card_id: str,
    data: UpdateCardRequest,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    card = await get_card(card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    if card.wallet != wallet.wallet.id:
        raise HTTPException(403, "Card does not belong to this wallet")
    # Update only provided (non-None) fields
    updates = {k: v for k, v in data.dict(exclude_none=True).items()}
    if updates:
        await update_card_fields(card_id, updates)
    return {"status": "updated"}
```

### Delete with Sats Reclaim
```python
# Source: codebase — services.py reclaim_card_sats() §165; crud.py mark_card_expired §84
@giftcards_api_router.delete("/{card_id}")
async def api_delete_card(
    card_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    card = await get_card(card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    if card.wallet != wallet.wallet.id:
        raise HTTPException(403, "Card does not belong to this wallet")
    if card.status == "redeemed":
        raise HTTPException(409, "Redeemed cards cannot be deleted")
    # Reclaim sats for active cards; expired cards already reclaimed
    if card.status == "active":
        await reclaim_card_sats(card)
    await delete_card(card.id)
    return {"status": "deleted", "reclaimed_sats": card.amount if card.status == "active" else 0}
```

### Quasar Multi-Select q-table
```html
<!-- Source: Quasar v2 docs — q-table selection prop [ASSUMED] -->
<q-table
  dense
  flat
  :rows="giftCards"
  row-key="id"
  :columns="giftCardColumns"
  selection="multiple"
  v-model:selected="selectedCards"
  v-model:pagination="tablePagination"
  :loading="loading"
>
  <!-- existing body template + new checkbox column handled by selection prop -->
</q-table>
```

### API Detail with include_link Flag
```python
# Source: codebase pattern — views_api.py; D-11
from fastapi import Query

class CardDetailResponse(BaseModel):
    card_id: str
    amount: int
    status: str
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    redeemed_at: Optional[datetime]
    email_status: Optional[str]
    redemption_url: Optional[str] = None  # only if include_link=true

@giftcards_api_router.get("/{card_id}")
async def api_get_card_detail(
    card_id: str,
    include_link: bool = Query(False, description="Include redemption URL in response"),
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> CardDetailResponse:
    card = await get_card(card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    if card.wallet != wallet.wallet.id:
        raise HTTPException(403, "Card does not belong to this wallet")
    return CardDetailResponse(
        card_id=card.id,
        amount=card.amount,
        status=card.status,
        recipient_name=card.recipient_name,
        sender_name=card.sender_name,
        message=card.message,
        created_at=card.created_at,
        expires_at=card.expires_at,
        redeemed_at=card.redeemed_at,
        email_status=card.email_status,
        redemption_url=card.redemption_url if include_link else None,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single card creation only | Bulk same-amount + CSV variable-amount | Phase 3 | Enables event/holiday/marketing use cases at scale |
| Admin-key-only API reads | Mixed auth: admin writes, invoice reads | Phase 3 (D-10) | External systems can poll status with read-only invoice key (lower privilege) |
| No redemption URL in API | `?include_link=true` opt-in flag | Phase 3 (D-11) | Balances security (raw_token not exposed by default) with integration needs |
| Simple card list (no filters) | Filterable dashboard (status, search, date) | Phase 3 (D-12) | Manageable at scale (hundreds/thousands of cards) |
| No card edit/delete | Edit metadata + delete with sats reclaim | Phase 3 (D-15, D-16) | Full card lifecycle management; hard delete with reclaim (soft delete/audit is v2) |

**Deprecated/outdated:**
- None for this phase — all patterns are current within the LNBits extension ecosystem.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Quasar `q-table` supports `selection="multiple"` + `v-model:selected` for multi-select checkboxes | Architecture Patterns, Code Examples | If not supported, would need custom checkbox column implementation. Low risk — this is a standard Quasar v2 feature. |
| A2 | Quasar `q-date` component is available in the LNBits-bundled Quasar version for date range picker | Standard Stack | If not available, would use two separate date inputs or a custom range picker. Low risk — q-date is a core Quasar component. |
| A3 | `ILIKE` is PostgreSQL-only; SQLite needs `LIKE` or `LOWER()` for case-insensitive search | Pitfall 3 | If wrong, query would fail on one DB type. Medium risk — must test on both SQLite (dev) and PostgreSQL (prod). |
| A4 | `csv.DictReader` handles BOM, quoted fields, and varied line endings correctly | Code Examples | If wrong, CSV parsing would fail on edge-case files. Low risk — DictReader is well-tested stdlib. Using `utf-8-sig` decode for BOM. |
| A5 | `asyncio.gather` with `Semaphore` is the right pattern for bounded concurrent SMTP sends | Pitfall 5 | If wrong, bulk email could overwhelm SMTP server or block event loop. Low risk — standard asyncio pattern. |
| A6 | The existing `GiftCardSummary.redemption_url` field is acceptable for admin-key dashboard but must be omitted from invoice-key API responses by default | Pitfall 4 | If wrong, security issue (raw_token exposed to invoice-key holders). Mitigated by using separate `CardDetailResponse` model for API. |

## Open Questions

1. **Should dashboard filtering be server-side or client-side?**
   - What we know: D-12 requires status dropdown, free-text search, date range. Current `get_cards_by_wallet()` returns all cards for a wallet.
   - What's unclear: Expected card volume per issuer. For <100 cards, client-side filtering is simpler. For >1000, server-side is necessary.
   - Recommendation: Implement server-side filtering (query params on `GET /cards`) — it scales and is not significantly more complex. The frontend sends filter params; the backend adds WHERE clauses. This is Claude's discretion per CONTEXT.md.

2. **Should "Send all emails" be synchronous or background?**
   - What we know: 500 emails × ~1s SMTP = ~8 minutes. CONTEXT.md defers this to planner's discretion.
   - What's unclear: Actual SMTP latency in the deployment environment.
   - Recommendation: Start with `asyncio.create_task` fire-and-forget (return immediately, send in background). Frontend polls `email_status` on cards for progress. If the issuer needs synchronous confirmation, add a `?wait=true` option later. This is the safer default for UX.

3. **Should the CSV export be client-side or server-side?**
   - What we know: Client-side `LNbits.utils.exportCSV` only exports loaded rows. Server-side `StreamingResponse` can export full filtered set.
   - What's unclear: Whether issuers will have more cards than the table page size.
   - Recommendation: Keep the existing client-side "Export CSV" button for quick export of loaded rows. Add a server-side `GET /cards/csv` endpoint for the "Download CSV (filtered)" global action that exports the full filtered set regardless of pagination.

4. **Does the `cancelled` status need a migration or is it just a string value?**
   - What we know: The `status` column is TEXT with no CHECK constraint. D-12 lists "cancelled" as a filter option. D-16 mentions deletion but not cancellation.
   - What's unclear: Whether Phase 3 introduces a "cancel" action (separate from delete) that sets status to "cancelled".
   - Recommendation: D-16 describes deletion (hard delete with reclaim), not cancellation. The "cancelled" filter in D-12 may be for forward compatibility with v2 AUDT-02. For Phase 3, include "cancelled" in the filter dropdown but no cancel action is needed. No migration needed for the status value itself (TEXT column accepts any string). An `updated_at` timestamp column (m004) is useful for tracking edit/delete timestamps.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10–3.12 | Extension runtime | ✓ | 3.12 (LNBits .venv) | — |
| FastAPI ~0.116.1 | API endpoints | ✓ | core dep | — |
| Pydantic v1 ~1.10.26 | Models | ✓ | core dep | — |
| `python-multipart` | CSV UploadFile | ✓ | core dep | — |
| `csv` (stdlib) | CSV parsing | ✓ | builtin | — |
| `asyncio` (stdlib) | Background tasks | ✓ | builtin | — |
| Pillow ~12.1.0 | Card image rendering (existing) | ✓ | core dep | — |
| pytest + pytest-asyncio | Tests | ✓ | .venv/bin/pytest | — |
| LNBits v1.5.4 | Runtime | ✓ | /home/exedev/lnbits | — |
| SQLite | Dev database | ✓ | builtin | PostgreSQL for prod |
| Quasar v2 (bundled) | Frontend components | ✓ | LNBits core | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

All dependencies are available in the LNBits `.venv` and core package set. No new installations needed.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | LNBits API key auth (`require_admin_key` / `require_invoice_key`) — wallet-scoped, key-derived |
| V3 Session Management | no | API keys are stateless bearer tokens; no session management needed |
| V4 Access Control | yes | Wallet ownership check on every update/delete (`card.wallet == wallet.wallet.id`); invoice key = read-only, admin key = write |
| V5 Input Validation | yes | Pydantic v1 models with `@validator` for all request bodies; CSV row validation before creation; 500-row limit |
| V6 Cryptography | yes | `secrets.token_urlsafe(32)` for token generation (existing); SHA-256 hash storage (existing); no new crypto needed |

### Known Threat Patterns for LNBits Extension API

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-wallet card access (IDOR) | Elevation of Privilege | Verify `card.wallet == wallet.wallet.id` on every update/delete/detail endpoint [VERIFIED: codebase — views_api.py §315] |
| raw_token leakage in API responses | Information Disclosure | `?include_link=true` opt-in flag; separate `CardDetailResponse` model without `redemption_url` by default (D-11) |
| CSV injection (formula injection) | Tampering | Strip/escape `=`, `+`, `-`, `@` at start of CSV cell values when exporting; validate on import |
| Bulk create wallet drain | Denial of Service | Pre-check total sats required vs. wallet balance before bulk loop; 500-row limit on CSV |
| Partial bulk creation on failure | Tampering | Two-phase CSV (validate → create); same-amount bulk has no per-row validation risk; log partial failures |
| SMTP credential exposure | Information Disclosure | Reuse LNBits core SMTP settings; never log passwords; catch SMTP exceptions without leaking details to client [VERIFIED: codebase — views_api.py §338] |
| CSV upload DoS (huge file) | Denial of Service | 500-row limit (D-08); reject files exceeding limit with 422 before parsing |
| Path traversal via CSV design columns | Tampering | Pydantic validators on `template_name`, `font_family` (existing allowlists in DesignConfig); validate per-row design columns against same allowlists |

## Sources

### Primary (HIGH confidence)
- Codebase inspection — `giftcards/services.py`, `models.py`, `views_api.py`, `crud.py`, `migrations.py`, `static/js/index.vue`, `static/js/index.js` (all read in this session)
- LNBits core — `lnbits/decorators.py` §204 (`require_invoice_key`), `lnbits/extensions/events/views_api.py` §155/§168 (mixed auth pattern), `lnbits/db.py` §164–§289 (DB methods), `lnbits/static/js/utils.js` §273 (`exportCSV`)
- `.planning/research/STACK.md` — dependency versions, forbidden libraries, CSV parsing guidance
- `.planning/phases/03-scale-manage/03-CONTEXT.md` — locked decisions D-01 through D-17

### Secondary (MEDIUM confidence)
- `.planning/research/SUMMARY.md` — architecture approach, layering conventions
- `.planning/STATE.md` — post-session decisions (no per-card wallets, raw_token in DB, proxy headers, Quasar `:model-value` binding)

### Tertiary (LOW confidence)
- Quasar v2 `q-table` selection and `q-date` component behavior — [ASSUMED] from training knowledge; standard Quasar features but not verified against the exact bundled version in this LNBits installation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified in codebase and LNBits core; no new packages
- Architecture: HIGH — all patterns derived from existing codebase inspection; no novel architecture
- Pitfalls: HIGH — derived from codebase patterns, STATE.md post-session notes, and CONTEXT.md decisions
- Security: HIGH — ASVS categories mapped to existing codebase controls; threat patterns derived from existing endpoint patterns

**Research date:** 2026-06-30
**Valid until:** 2026-07-30 (30 days — stable codebase, no external API dependencies)

## RESEARCH COMPLETE
