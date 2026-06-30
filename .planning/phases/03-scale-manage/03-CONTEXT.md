# Phase 3: Scale & Manage - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers bulk gift card creation (same-amount form + CSV upload with per-row validation), a REST API for external card creation and status lookup, and a filterable issuer dashboard with card detail view, editing, and deletion. The single-card creation flow from Phase 1 and the branded delivery from Phase 2 scale up to batch operations and external automation.

**In scope:**
- Bulk same-amount creation: number input for quantity, separate "Bulk Create" button + dialog
- Bulk CSV upload: required columns (recipient_name, amount_sats), optional columns (recipient_email, nostr_npub, sender_name, message), per-row design columns optional
- CSV validation: per-row validation table + summary, all rows must pass before any cards created (BULK-03)
- CSV row limit: 500 rows max
- REST API: mirror existing card endpoints + dedicated bulk endpoint, admin key for writes, invoice key for reads
- Card status/detail API with optional `?include_link=true` flag for redemption URL
- Dashboard filters: status dropdown, free-text search, date range picker
- Card detail: expand row for quick view + detail dialog for full info
- Card editing: all fields, but amount change requires cancel + recreate
- Card deletion: non-redeemed cards only, reclaim sats first then delete record
- Bulk dashboard actions: global buttons (Send all filtered, Download CSV filtered) + multi-select checkboxes for targeted actions

**Out of scope (deferred):**
- Nostr delivery (DELV-03) — still deferred from Phase 2
- Audit log per card (AUDT-01) — v2
- Cancel/soft-delete with audit trail (AUDT-02) — v2 (Phase 3 does hard delete with sats reclaim)
- Printable PDF / cut sheet (PRNT-01) — v2
- SMS delivery (PRNT-02) — v2

</domain>

<decisions>
## Implementation Decisions

### Bulk Creation UI
- **D-01:** Separate "Bulk Create" button next to the existing "Create Gift Card" button. Opens a dedicated bulk dialog distinct from the single-card create dialog. Two entry points, two dialogs.
- **D-02:** Same-amount bulk uses a simple number input for quantity ("How many cards?"). Issuer types a number (e.g., 50). No slider, no dynamic recipient list. Cleanest UI for known quantities.
- **D-03:** After bulk creation: toast notification + dashboard refresh. The dashboard IS the results view. No dedicated results table in the dialog. The newly created cards appear in the filtered dashboard.
- **D-04:** "Download CSV" and "Send all emails" are available as dashboard actions (both global and per-selection — see D-12). Issuer exports links or triggers delivery from the dashboard after bulk creation.

### CSV Upload Format
- **D-05:** Required columns: `recipient_name`, `amount_sats`. Optional columns: `recipient_email`, `nostr_npub`, `sender_name`, `message`. Email/npub are optional since not all cards need delivery. Matches BULK-02 spec.
- **D-06:** CSV design mode is a three-way choice in the bulk dialog:
  - "No design" — cards created with bare QR (Phase 1 style), no template/QR/text config
  - "One design for all rows" — issuer picks a design (template + QR + text styling) once in the bulk dialog, applied uniformly to every CSV row
  - "Per-row design columns" — CSV includes optional design columns (template_name, qr_x, qr_y, qr_size, text_x, text_y, font_size, font_color, etc.) for per-card customization
- **D-07:** CSV validation shows BOTH a per-row validation table (green check / red error per row) AND a summary ("X valid, Y errors"). Issuer must fix all errors before proceeding — no partial create. Matches BULK-03 exactly.
- **D-08:** Maximum 500 rows per CSV upload. Keeps the request responsive (500 card creations + funding in one batch). Planner should validate row count on upload and reject files exceeding the limit with a clear error.

### REST API Design
- **D-09:** API mirrors existing card endpoints + adds a dedicated bulk endpoint. `POST /giftcards/api/v1/cards` (single create, existing), `POST /giftcards/api/v1/cards/bulk` (bulk create, new), `GET /giftcards/api/v1/cards` (list, existing), `GET /giftcards/api/v1/cards/{id}` (detail, existing). Minimal new code, consistent with existing patterns.
- **D-10:** Admin key required for all write operations (create, bulk create, delete, update). Invoice key accepted for all read operations (list, detail, status). Satisfies API-03 and fulfills D-11 deferred from Phase 1.
- **D-11:** Card status/detail API response includes: card_id, amount, status, recipient_name, sender_name, created_at, expires_at, redeemed_at, email_status. Redemption URL is NOT included by default. An optional `?include_link=true` query flag adds the redemption_url to the response. External systems opt in to receiving the link. This balances security (raw_token not exposed by default) with integration needs.

### Dashboard Filters & Detail View
- **D-12:** Dashboard filters: status dropdown (created, active, redeemed, expired, cancelled) + free-text search (searches recipient name, sender name, card ID) + date range picker (created_at between X and Y). Covers DASH-02 for common filter use cases.
- **D-13:** Card detail view is a hybrid: expand row in the q-table for quick view (summary + key actions), plus a "View full details" button in the expanded row that opens a detail dialog with everything including branded image preview. No separate route/page.
- **D-14:** Bulk dashboard actions: BOTH global buttons above the table ("Send all (filtered)", "Download CSV (filtered)") AND multi-select checkboxes on rows for targeted actions on specific cards. Global buttons apply to all filtered cards; multi-select applies to checked cards only.

### Card Editing & Deletion
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project requirements and research
- `.planning/PROJECT.md` — Project scope, core value, constraints, and key decisions. Notes bulk CSV + API as Phase 3 scope.
- `.planning/REQUIREMENTS.md` — v1 requirements; Phase 3 covers BULK-01 through BULK-04, API-01 through API-03, DASH-01 through DASH-03.
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria, and dependencies.
- `.planning/research/SUMMARY.md` — Research conclusions: stack, architecture, pitfalls. Line 56 notes bulk performance considerations.
- `.planning/research/ARCHITECTURE.md` — LNBits extension anatomy and component boundaries.

### Prior phase context
- `.planning/phases/01-core-loop/01-CONTEXT.md` — Phase 1 decisions: D-01 (LNURL-withdraw), D-05/D-06 (token security with secrets.token_urlsafe + SHA-256 hash), D-11 (invoice-key deferred to Phase 3 — NOW ACTIVE), D-13 (DB namespace ext_giftcards).
- `.planning/phases/02-branded-delivery/02-CONTEXT.md` — Phase 2 decisions: D-15 (magic link reveals list of pending cards for same email — bulk CSV sets up this flow), D-24 (create first, deliver later — bulk follows this pattern), D-25 (recipient_email optional at creation — CSV email column is optional).

### Current giftcards extension (code to extend)
- `giftcards/views_api.py` — Existing API endpoints: create card (§58), list cards (§76), lnurl/redeem endpoints. Add bulk create, update, delete endpoints. Switch list/detail to accept invoice key.
- `giftcards/models.py` — Current models: GiftCard, CreateGiftCard, GiftCardSummary, PublicGiftCard, DesignConfig, DeliverRequest. Add bulk create request model, update model, CSV row model.
- `giftcards/crud.py` — Current CRUD: get_cards_by_wallet (§35), create_card, update_card_email_status. Add bulk create, update card fields, delete card with sats reclaim.
- `giftcards/services.py` — Current services: create_gift_card (funds card), render_card_image, send_gift_card_email. Add bulk creation orchestration, CSV parsing/validation, sats reclaim on delete.
- `giftcards/static/js/index.vue` — Current issuer UI: create dialog, card list q-table with expand. Add bulk create button + dialog, dashboard filters, multi-select, detail dialog, edit dialog, delete confirmation.
- `giftcards/static/js/index.js` — Current JS: giftCardColumns, createGiftCard, loadGiftCards. Add bulk creation, filtering, editing, deletion, CSV export.
- `giftcards/migrations.py` — Current migrations: m001_initial, m002_add_raw_token, m003 (Phase 2 fields). Add m004 if new fields needed (e.g., cancelled status, updated_at timestamp).

### LNBits core (auth patterns)
- `/home/exedev/lnbits/lnbits/decorators.py` §204 — `require_invoice_key` decorator. Now used for Phase 3 read endpoints.
- `/home/exedev/events/views_api.py` §29, §155 — Events extension uses both `require_admin_key` and `require_invoice_key` — reference pattern for mixed auth.

### Reference codebase (events extension — CSV/bulk patterns)
- `/home/exedev/events/views_api.py` — Events extension API patterns for reference (no direct CSV bulk, but auth + CRUD patterns apply).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_gift_card()` in `giftcards/services.py` — Single card creation with wallet debit. Bulk creation calls this in a loop (or batched transaction). Already handles funding, token generation, DB insert.
- `get_cards_by_wallet()` in `giftcards/crud.py` — Returns `list[GiftCardSummary]`. Dashboard list already uses this. Add filtering (status, date range, search) to the query or filter client-side.
- `send_gift_card_email()` in `giftcards/services.py` — Email delivery. "Send all emails" bulk action calls this per card with recipient_email.
- `render_card_image()` in `giftcards/services.py` — Branded card rendering. CSV "one design for all" mode uses this with a shared DesignConfig.
- `giftCardColumns` in `giftcards/static/js/index.js` — Existing q-table column definitions. Extend with multi-select checkboxes and filter controls.
- `require_invoice_key` from `lnbits.decorators` — Now activated for Phase 3 read-only API endpoints.
- Python stdlib `csv` module — For CSV parsing. No new dependency needed.

### Established Patterns
- Pydantic v1 models with `@validator` — Add BulkCreateRequest, CSVRow, UpdateCard models.
- `require_admin_key` / `require_invoice_key` decorators — Auth pattern for API endpoints.
- `asyncio.to_thread()` — Offload CPU-bound work (CSV parsing for 500 rows is lightweight, but image rendering for bulk delivery may need it).
- Quasar q-table with expand row — Current card list pattern. Extend with filters and multi-select.
- `StreamingResponse` for file downloads — CSV export endpoint returns a StreamingResponse with CSV content.
- Migrations: sequential `mNNN_name(db)` functions. Add m004 if new columns needed.

### Integration Points
- `giftcards/views_api.py` — Add: `POST /cards/bulk`, `PUT /cards/{id}` (update), `DELETE /cards/{id}` (delete), `GET /cards/csv` (export). Switch `GET /cards` and `GET /cards/{id}` to accept `require_invoice_key` OR `require_admin_key`.
- `giftcards/models.py` — Add: `BulkCreateRequest` (amount + count + optional design config), `CSVUploadRequest`, `CSVRow` (validation model), `UpdateCardRequest`, `CardDetailResponse` (with optional redemption_url).
- `giftcards/crud.py` — Add: `bulk_create_cards()`, `update_card()`, `delete_card()`, `get_cards_by_wallet_filtered()` (status, date range, search).
- `giftcards/services.py` — Add: `parse_csv()`, `validate_csv_rows()`, `bulk_create_with_funding()`, `reclaim_sats_and_delete()`, `export_cards_csv()`.
- `giftcards/static/js/index.vue` — Add: Bulk Create button + dialog, filter controls (status dropdown, search input, date range), multi-select checkboxes, detail dialog, edit dialog, delete confirmation, global bulk action buttons.
- `giftcards/static/js/index.js` — Add: bulk creation logic, CSV upload + validation display, filtering logic, edit/delete handlers, CSV export, multi-select bulk actions.

</code_context>

<specifics>
## Specific Ideas

- The bulk dialog should have two tabs: "Same Amount" (number input + amount + optional design) and "CSV Upload" (file picker + validation table + design mode selector). Both tabs share the same "Bulk Create" button.
- CSV design mode selector appears only in the CSV tab: "No design" / "One design for all" / "Per-row design columns". When "One design for all" is selected, the card designer UI (from Phase 2) appears in the dialog for the issuer to configure the shared design.
- The dashboard should feel like a management console — filters at the top, table with checkboxes, global action buttons above the table. Not just a list anymore.
- Edit dialog should look similar to the create dialog but pre-filled. Amount field shows a notice that changing it requires cancel + recreate.
- Delete confirmation should show the sats amount being reclaimed: "This will reclaim 500 sats to your wallet and permanently delete this card."
- "Send all (filtered)" should show a progress indicator if sending to many recipients — SMTP latency for 500 emails could be significant.
- CSV export should include all card fields: card_id, amount, status, recipient_name, sender_name, message, recipient_email, email_status, redemption_url, created_at, expires_at, redeemed_at.

</specifics>

<deferred>
## Deferred Ideas

- **Nostr delivery (DELV-03)** — Still deferred from Phase 2. LNBits core has `send_nostr_dm()` infrastructure. Future phase.
- **Audit log per card (AUDT-01)** — v2. Phase 3 does hard delete with no audit trail. AUDT-02 soft delete/cancel with audit trail is v2.
- **Printable PDF / cut sheet (PRNT-01)** — v2. Phase 3 focuses on CSV export of card data, not print-optimized layouts.
- **SMS delivery (PRNT-02)** — v2. Pluggable provider model.
- **Background job for bulk email sending** — If "Send all emails" for 500 cards is too slow synchronously, a background task with progress tracking could be added. For now, planner's discretion on sync vs async.
- **Webhook notifications for card status changes** — External systems polling the API is sufficient for v1. Webhooks could be a future enhancement.
- **Rate limiting on API endpoints** — Phase 3 adds the API surface but rate limiting on API calls is deferred (Phase 1 D-06 deferred rate limiting to Phase 6; API rate limiting follows the same pattern).

</deferred>

---

*Phase: 3-Scale & Manage*
*Context gathered: 2026-06-30*
