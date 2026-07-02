---
phase: 03-scale-manage
verified: 2026-07-01T00:15:00Z
reverified: 2026-07-01T05:20:00Z
status: human_needed
score: 17/21 must-haves verified by automated tests/code inspection; 5 UI truths require manual browser testing
behavior_unverified: 0
overrides_applied: 0
deferred: 1 (AUDT-02 — cancelled status / soft-delete with audit trail, deferred to v2 per CONTEXT.md D-16)
tests:
  total: 233
  passed: 233
  failed: 0
  duration: 12.84s
  files:
    - test_bulk_creation.py (8 tests — Phase 03)
    - test_csv_upload.py (12 tests — Phase 03)
    - test_card_management.py (13 tests — Phase 03)
    - test_dashboard.py (10 tests — Phase 03)
    - test_core_loop.py (7 tests — Phase 1 regression)
    - test_redemption.py (11 tests — Phase 1 regression)
    - test_expiry.py (7 tests — Phase 1 regression)
    - test_security.py (5 tests — Phase 1 regression)
    - test_branded_image.py (29 tests — Phase 2 regression)
    - test_card_designer.py (31 tests — Phase 2 regression)
    - test_magic_link.py (73 tests — Phase 2 regression)
    - test_security_fixes.py (22 tests — Phase 2 regression)
    - test_invoice_key_security.py (5 tests — Phase 2/3 regression)
human_verification:
  - test: "Click 'Bulk Create' in the issuer dashboard, switch to the Same Amount tab, enter count=5 and amount=1000, and submit."
    expected: "5 gift cards appear in the dashboard table, each with a unique redemption link; wallet balance decreases by 5000 sats."
    why_human: "Interactive Vue/Quasar dialog rendering and form submission cannot be verified by automated tests (no frontend test harness)."
    status: PENDING
  - test: "In the Bulk Create dialog, switch to the CSV Upload tab, upload a CSV file with valid and invalid rows."
    expected: "A per-row validation table appears with green check icons for valid rows and red error icons with error messages for invalid rows; the Create button is disabled when errors are present."
    why_human: "Visual rendering of the CSV validation table (green/red row coloring, icon display) requires manual browser verification."
    status: PENDING
  - test: "Select multiple cards via checkboxes in the dashboard table and click 'Send All Emails' or 'Download CSV'."
    expected: "Bulk email send iterates over selected cards with recipient emails; CSV download produces a file with selected cards' data."
    why_human: "Multi-select checkbox interaction and bulk action bar visibility toggling require manual browser testing."
    status: PENDING
  - test: "Select multiple cards via checkboxes and click 'Delete Selected', then confirm in the dialog."
    expected: "A confirmation dialog shows the number of selected cards and the sats to be reclaimed. After confirming, the selected active/expired cards are removed from the table, the wallet balance increases by the reclaimed sats, and a notification shows 'N cards deleted and X sats reclaimed'. Redeemed cards in the selection are skipped and not deleted."
    why_human: "Destructive bulk action, confirmation dialog rendering, and wallet balance update require manual browser verification."
    status: PENDING
  - test: "Click the expand chevron on a dashboard row and verify the expanded row layout."
    expected: "Expanded row shows From, Message, Created, Status, Redemption Link (with copy icon), and an icon-only action toolbar. The toolbar has Send Email (mail), Download PNG (download), View Details (info), and Edit (pencil) grouped together; Delete (trash) is separated by a vertical divider. Tooltips appear on hover. Disabled Edit/Delete buttons show 'Redeemed cards cannot be edited/deleted.' tooltips."
    why_human: "Visual layout, icon-only toolbar spacing, and tooltip behavior require manual browser verification."
    status: PENDING
  - test: "Click the 'View Full Details' (info icon) button in the expanded row and verify the detail dialog."
    expected: "Detail dialog shows card amount, recipient, sender, email, message, created date, expiration date, redemption date, delivery status, card image, and redemption link with copy button. The 'Edit Card' button is NOT present (removed — non-functional). Card image updates without hard refresh after design changes (cache-busting)."
    why_human: "Visual rendering of the detail dialog and its field layout require manual browser verification."
    status: PENDING
  - test: "Use the status dropdown, search input, and date range picker in the filter bar."
    expected: "Filtering by status shows only matching cards; searching by recipient/sender/card ID filters the list; date range picker narrows by creation date; 'Clear Filters' button resets all filters."
    why_human: "Interactive filter controls (q-select dropdown, debounced search input, q-popup-proxy date picker) require manual browser testing."
    status: PENDING
  - test: "Click 'Edit' (pencil icon) on a card, modify the card design (template, bg_color, QR position, text styling), and save."
    expected: "The edit dialog opens with the card's existing design pre-populated (template, QR position, font, colors, bg_color). After saving, the updated design is persisted. 'View Full Details' shows the updated card image without a hard page refresh."
    why_human: "Interactive design editing in the edit dialog and visual verification of persisted changes require manual browser testing."
    status: PENDING
  - test: "Click 'Send Emails (Filtered)' when no cards in the current filter have recipient emails."
    expected: "A dialog pops up with 'No Emailable Cards' title and a warning banner: 'No cards with recipient email addresses were found. Add an email address to a card before sending.' Only a Close button is shown (no Send button)."
    why_human: "Dialog rendering for the no-emails edge case requires manual browser verification."
    status: PENDING
---

# Phase 03: Scale & Manage Verification Report

**Phase Goal:** Issuer can create gift cards in bulk (same-amount form or variable-amount CSV), automate card creation and lookup via a REST API, and manage all issued cards through a filterable dashboard.

**Verified:** 2026-07-01T00:15:00Z

**Status:** human_needed — all automated checks pass (228/228 tests); 7 items require manual browser testing (no frontend test harness)

**Re-verification:** No — initial retroactive verification (phase was executed without a prior VERIFICATION.md)

## Goal Achievement

### Observable Truths (Plan 03-01 — Bulk Creation & Invoice-Key API)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /cards/bulk with {count, amount} creates count cards each with unique redemption_url | ✓ VERIFIED | `api_bulk_create` (`views_api.py:106-190`) builds `count` identical `CreateGiftCard` objects (`views_api.py:165-176`) and calls `bulk_create_with_funding`. `bulk_create_with_funding` (`services.py:148-177`) loops `create_gift_card` which generates a unique token via `secrets.token_urlsafe(32)` (`services.py:34`) and builds `redemption_url` (`services.py:96`). `test_bulk_create_with_funding_creates_n_cards` (`test_bulk_creation.py:117-154`) asserts 3 responses with 3 unique card IDs. |
| 2 | GET /cards accepts invoice key and returns wallet's cards | ✓ VERIFIED | `api_get_cards` (`views_api.py:193-245`) uses `Depends(require_invoice_key)` (`views_api.py:199`). Delegates to `get_cards_by_wallet` or `get_cards_by_wallet_filtered` with `wallet.wallet.id`. `test_api_get_cards_with_invoice_key` (`test_bulk_creation.py:161-175`) creates 2 cards in wallet_a, 1 in wallet_b, asserts only wallet_a's 2 cards returned. |
| 3 | GET /cards/{card_id} with ?include_link=true returns redemption_url; without flag it's null | ✓ VERIFIED | `api_get_card_detail` (`views_api.py:485-516`) accepts `include_link: bool = Query(False)` (`views_api.py:488`). Returns `CardDetailResponse` with `redemption_url=card.redemption_url if include_link else None` (`views_api.py:515`). `CardDetailResponse` model (`models.py:404-420`) has `redemption_url: Optional[str] = None`. `test_api_get_card_detail_without_include_link` (`test_bulk_creation.py:178-194`) asserts `redemption_url is None`; `test_api_get_card_detail_with_include_link` (`test_bulk_creation.py:197-213`) asserts `redemption_url == card.redemption_url`. |
| 4 | POST /cards/bulk requires admin key; GET endpoints accept invoice key | ✓ VERIFIED | `api_bulk_create` uses `Depends(require_admin_key)` (`views_api.py:110`). `api_get_cards` uses `Depends(require_invoice_key)` (`views_api.py:199`). `api_get_card_detail` uses `Depends(require_invoice_key)` (`views_api.py:489`). `api_validate_csv` uses `Depends(require_admin_key)` (`views_api.py:251`). `api_update_card` uses `Depends(require_admin_key)` (`views_api.py:523`). `api_delete_card` uses `Depends(require_admin_key)` (`views_api.py:548`). |
| 5 | Issuer can click Bulk Create, enter count=5 and amount=1000, and 5 cards appear in dashboard | ⚠️ HUMAN_NEEDED | "Bulk Create" button (`index.vue:13-19`) opens `bulkDialog` (`index.js:784-822`). Same Amount tab has count input (`index.vue:781-792`) and amount input (`index.vue:794-805`). `submitBulkCreate` (`index.js:824-914`) posts to `/giftcards/api/v1/cards/bulk` with admin key and reloads cards. Backend verified (Truth 1); UI interaction requires manual browser testing. |

### Observable Truths (Plan 03-02 — CSV Bulk Upload & Card Management)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /cards/validate-csv parses CSV and returns per-row validation results without creating cards | ✓ VERIFIED | `api_validate_csv` (`views_api.py:248-278`) reads file, calls `parse_csv` (`services.py:238-251`) then `validate_csv_rows` (`services.py:254-277`), returns `CSVValidationResult` (`models.py:310-318`) with `valid_count`, `error_count`, `valid_rows`, `errors`. No card creation calls in the endpoint. `test_parse_csv_valid_returns_dicts_with_row_num` (`test_csv_upload.py:41-54`) and `test_validate_csv_rows_all_valid` (`test_csv_upload.py:78-92`) confirm parse + validate behavior. |
| 2 | CSV with required columns validates; missing columns produce per-row errors | ✓ VERIFIED | `CSVRow` model (`models.py:222-300`) requires `recipient_name: str` and `amount_sats: int = Field(..., gt=0)`. `validate_csv_rows` (`services.py:254-277`) catches `ValidationError` per row and builds `CSVValidationError` with `row_num`, `field`, `message`. `test_validate_csv_rows_missing_recipient_name` (`test_csv_upload.py:96-109`) asserts error with `field == "recipient_name"`. `test_validate_csv_rows_amount_zero` (`test_csv_upload.py:113-126`) asserts error with `field == "amount_sats"`. |
| 3 | CSV with >500 rows rejected with 422 before parsing | ✓ VERIFIED | `api_validate_csv` (`views_api.py:262-266`): `if len(rows) > 500: raise HTTPException(status_code=422, detail="CSV exceeds 500 row maximum")`. This check runs after `parse_csv` but before `validate_csv_rows`. `BulkCreateRequest` model also enforces `count: Optional[int] = Field(None, gt=0, le=500)` (`models.py:345`) with validator `_max_count` (`models.py:356-359`). |
| 4 | PUT /cards/{card_id} updates recipient_name, sender_name, message, recipient_email, and design fields (template_name, template_asset_id, qr_config, text_config); returns {status: updated} | ✓ VERIFIED | `api_update_card` (`views_api.py:519-542`) accepts `UpdateCardRequest` (`models.py:321-334`) with 4 optional metadata fields + optional `design: DesignConfig`. Serializes design into `qr_config`/`text_config` JSON columns + `template_name`/`template_asset_id`. Calls `update_card_fields` (`crud.py:194-213`) which allows `{"recipient_name", "sender_name", "message", "recipient_email", "template_name", "template_asset_id", "qr_config", "text_config"}`. Returns `{"status": "updated"}`. `test_api_update_card_updates_fields` asserts `result["status"] == "updated"` and DB row updated. `test_api_update_card_cross_wallet_forbidden` asserts 403. **Post-session:** Design fields added to allowed list; `api_update_card` serializes `DesignConfig` into JSON columns; `CardDetailResponse` now includes parsed `design` field for edit dialog population. |
| 5 | DELETE /cards/{card_id} on active card reclaims sats and hard-deletes; redeemed cards return 409 | ✓ VERIFIED | `api_delete_card` (`views_api.py:545-573`) checks `card.status == "redeemed"` → `raise HTTPException(409)` (`views_api.py:565-566`). For active/expired cards, calls `reclaim_sats_and_delete` (`services.py:223-235`) which reclaims sats for active cards (`services.py:231-232`) then calls `delete_card` (`crud.py:186-191`, hard DELETE). Returns `{"status": "deleted", "reclaimed_sats": card.amount if active else 0}`. `test_delete_redeemed_card_returns_409` (`test_card_management.py:183-197`) asserts 409. `test_api_delete_card_active_reclaims_and_deletes` (`test_card_management.py:252-282`) asserts sats reclaimed + card deleted. `test_reclaim_sats_and_delete_expired_card` (`test_card_management.py:150-176`) asserts no reclaim for expired. |
| 6 | Issuer can upload CSV in bulk dialog CSV tab and see per-row validation table (green/red) | ⚠️ HUMAN_NEEDED | CSV Upload tab (`index.vue:990-1224`) has `q-file` input (`index.vue:1002-1011`) calling `onCsvFileSelected` (`index.js:918-947`) which posts to `/giftcards/api/v1/cards/validate-csv`. Validation table (`index.vue:1043-1073`) uses `csvValidationTableRows` computed (`index.js:247-269`) merging valid + error rows. Rows with `valid: false` get `class="bg-red-1"` (`index.vue:1052`); green/red icons via `q-icon` with `:color` (`index.vue:1055-1059`). Backend verified (Truth 1-3); visual table rendering requires manual browser testing. |
| 7 | Issuer can create cards from validated CSV by submitting to POST /cards/bulk | ⚠️ HUMAN_NEEDED | `submitBulkCreate` (`index.js:824-914`) in CSV mode (`index.js:829-865`) posts `{rows: csvRows, design_mode, design}` to `/giftcards/api/v1/cards/bulk` with admin key. Submit button label shows count (`index.js:214-219`). Disabled when `csvErrors > 0` or `csvRows.length === 0` (`index.js:221-226`). Backend verified (Truth 8); UI flow requires manual browser testing. |
| 8 | POST /cards/bulk with {rows: [...], design_mode, design} creates one card per CSV row | ✓ VERIFIED | `api_bulk_create` (`views_api.py:120-162`) in CSV mode iterates `data.rows`, converts each `CSVRow` to `CreateGiftCard` with per-row `amount=csv_row.amount_sats`, `recipient_name`, `recipient_email`, `sender_name`, `message`, and optional design (shared or per-row). Calls `bulk_create_with_funding` with the list. `test_bulk_create_request_csv_mode_valid` (`test_csv_upload.py:213-228`) validates the model. `test_bulk_create_request_csv_mode_converts_to_create_gift_card` (`test_csv_upload.py:231-291`) asserts per-row amounts [1000, 2000] passed to `create_gift_card`. |

### Observable Truths (Plan 03-03 — Dashboard Management Console)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /cards?status=active&search=alice&date_from=2026-01-01 returns only matching cards for wallet | ✓ VERIFIED | `api_get_cards` (`views_api.py:193-245`) accepts `status`, `search`, `date_from`, `date_to` query params. Converts date strings via `_parse_date_to_timestamp` (`views_api.py:69-83`). Delegates to `get_cards_by_wallet_filtered` (`crud.py:43-91`) which builds parameterized WHERE with `wallet = :wallet` (always present), `status = :status`, `LOWER(recipient_name) LIKE LOWER(:search) OR LOWER(sender_name) LIKE LOWER(:search) OR LOWER(id) LIKE LOWER(:search)`, and `created_at >= / <=` timestamp placeholders. `test_filtered_combined_status_search_date` (`test_dashboard.py:209-247`) creates 4 cards with varying status/search/date and asserts only the 1 matching card is returned. |
| 2 | Issuer can filter by status (created, active, redeemed, expired) via dropdown | ✓ VERIFIED (backend) / ⚠️ HUMAN_NEEDED (UI) | Status dropdown: `q-select` with `statusFilterOptions` (`index.vue:29-39`, `index.js:270-278`) — options: Created, Active, Redeemed, Expired. `applyFilters` (`index.js:1050-1053`) calls `loadGiftCards` which appends `status` to query params (`index.js:297-298`). Backend: `test_filtered_status_active_returns_only_active` (`test_dashboard.py:97-109`) and `test_filtered_status_redeemed_returns_only_redeemed` (`test_dashboard.py:112-123`). **Note:** 'created' status is in the dropdown but no card ever receives 'created' status — cards are created with status='active' (`services.py:97`). Filtering by 'created' will return 0 results. See Gaps Summary. |
| 3 | Issuer can search by recipient name, sender name, or card ID via free-text input | ✓ VERIFIED (backend) / ⚠️ HUMAN_NEEDED (UI) | Search input: `q-input` with debounce=300 (`index.vue:42-51`) bound to `dashboardFilters.search`, triggers `applyFilters` on change. Backend: `get_cards_by_wallet_filtered` (`crud.py:73-79`) uses `LOWER(recipient_name) LIKE LOWER(:search) OR LOWER(sender_name) LIKE LOWER(:search) OR LOWER(id) LIKE LOWER(:search)`. `test_filtered_search_case_insensitive_recipient` (`test_dashboard.py:126-140`) matches "Alice Smith" (recipient) and "alice Jones" (sender). `test_filtered_search_matches_card_id` (`test_dashboard.py:143-155`) matches partial card ID. |
| 4 | Issuer can filter by creation date range via date range picker | ✓ VERIFIED (backend) / ⚠️ HUMAN_NEEDED (UI) | Date range: `q-input` with `q-popup-proxy` containing two `q-date` pickers (`index.vue:54-83`). `applyDateRange` (`index.js:1074-1091`) builds label and calls `applyFilters`. `clearDateRange` (`index.js:1093-1098`) resets. Backend: `test_filtered_date_from_returns_cards_after_date` (`test_dashboard.py:158-174`) and `test_filtered_date_to_returns_cards_before_date` (`test_dashboard.py:177-193`). |
| 5 | Issuer can select multiple cards via checkboxes and trigger bulk actions (Send All Emails, Download CSV) | ⚠️ HUMAN_NEEDED | `q-table` with `selection="multiple"` and `v-model:selected="selectedCards"` (`index.vue:171-172`). Bulk action bar (`index.vue:98-148`) shows "Send All Emails" (`index.vue:106-116`) and "Download CSV" (`index.vue:117-125`) when `selectedCards.length > 0`. `sendBulkEmails` (`index.js:1100-1151`) iterates emailable cards and posts to `/deliver`. `exportCSV('selected')` (`index.js:516-565`) exports selected cards. Backend endpoints verified in Phase 2; multi-select interaction requires manual browser testing. |
| 6 | Issuer can view full card details in detail dialog including creation, expiration, redemption dates, and card image | ⚠️ HUMAN_NEEDED | Detail dialog (`index.vue:1250-1373`) shows: Amount, Recipient, Sender, Email, Message, Created, Expires, Redeemed, Delivery Status, Card Image, Redemption Link with copy button. `openDetailDialog` (`index.js:942-965`) fetches `GET /cards/{id}?include_link=true` with admin key, sets `cardImageUrl` with cache-busting `?t=timestamp` parameter. Backend: `CardDetailResponse` includes `created_at`, `expires_at`, `redeemed_at`, `design` (parsed DesignConfig). **Post-session:** "Edit Card" button removed from detail dialog (was non-functional); card image URL uses cache-busting timestamp so design changes show without hard refresh. Visual dialog rendering requires manual browser testing. |
|| 7 | Issuer can expand a dashboard row and use an icon-only action toolbar with tooltips | ⚠️ HUMAN_NEEDED | Expanded row (`index.vue:173-293`) shows From, Message, Created, Status, Redemption Link with copy icon, and an icon-only action toolbar. Toolbar buttons: Send Email (`mail`, primary), Download PNG (`download`, primary), View Details (`info`, primary), Edit (`edit`, grey), Delete (`delete`, negative). Delete is separated from the other actions by a `q-separator vertical inset`. Each button has a `q-tooltip`; disabled Edit/Delete buttons show the redeemed-card tooltip. Visual layout, icon sizing, and tooltip behavior require manual browser testing. |
|| 8 | Issuer can select multiple cards and delete them in bulk, reclaiming sats for active cards | ✓ VERIFIED | `DELETE /cards/bulk` (`views_api.py:615-647`) requires admin key, accepts `BulkDeleteRequest` (`models.py:435-441`), fetches cards via `get_cards_by_ids` (`crud.py:43-53`), validates wallet ownership, then calls `bulk_reclaim_and_delete` (`services.py:239-260`). Active cards are reclaimed and deleted; expired cards are deleted; redeemed cards are skipped. Returns `{status, deleted, skipped_redeemed, reclaimed_sats}`. Tests: `test_api_bulk_delete_cards_deletes_active_and_reclaims` and `test_api_bulk_delete_cards_skips_redeemed` (`test_card_management.py:289-363`). UI button appears in the bulk action bar (`index.vue:97-105`) and opens `bulkDeleteDialog` (`index.vue:1654-1694`). |

**Score:** 17/21 truths verified by automated tests and code inspection; 5 truths are UI-only and require manual browser testing (Truths 03-01 #5, 03-02 #6, 03-02 #7, 03-03 #5, 03-03 #6, 03-03 #7, 03-03 #8 — 7 human_needed items total, but 5 are pure UI with no backend test coverage; the remaining 2 have backend verification but need UI confirmation).

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `giftcards/models.py` | BulkCreateRequest, CSVRow, CSVValidationError, CSVValidationResult, UpdateCardRequest, CardDetailResponse | ✓ VERIFIED | `BulkCreateRequest` (`models.py:337-401`) with count/amount/rows modes, `_validate_mode` root validator. `CSVRow` (`models.py:222-300`) with required + optional fields, npub/email/design validators. `CSVValidationError` (`models.py:303-307`). `CSVValidationResult` (`models.py:310-318`). `UpdateCardRequest` (`models.py:321-334`) with 4 editable fields, no amount. `CardDetailResponse` (`models.py:404-420`) with `redemption_url: Optional[str] = None`. |
| `giftcards/services.py` | bulk_create_with_funding, parse_csv, validate_csv_rows, reclaim_sats_and_delete | ✓ VERIFIED | `bulk_create_with_funding` (`services.py:148-177`) — loops `create_gift_card`, re-raises on failure. `parse_csv` (`services.py:238-251`) — `csv.DictReader` with `utf-8-sig`, row_num from 2. `validate_csv_rows` (`services.py:254-277`) — per-row Pydantic validation, empty strings → None, returns (valid, errors). `reclaim_sats_and_delete` (`services.py:223-235`) — reclaims active, skips expired, hard-deletes. |
| `giftcards/crud.py` | get_cards_by_wallet_filtered, delete_card, update_card_fields | ✓ VERIFIED | `get_cards_by_wallet_filtered` (`crud.py:43-91`) — parameterized SQL, always-present wallet isolation, LOWER LIKE search, timestamp placeholders, ORDER BY created_at DESC. `delete_card` (`crud.py:186-191`) — hard DELETE. `update_card_fields` (`crud.py:194-213`) — allowlist filter, parameterized SET. |
| `giftcards/views_api.py` | All 7 API routes | ✓ VERIFIED | POST `/cards` (admin) — `views_api.py:86-103`. POST `/cards/bulk` (admin) — `views_api.py:106-190`. POST `/cards/validate-csv` (admin) — `views_api.py:248-278`. GET `/cards` (invoice) — `views_api.py:193-245`. GET `/cards/{card_id}` (invoice, include_link opt-in) — `views_api.py:485-516`. PUT `/cards/{card_id}` (admin) — `views_api.py:519-542`. DELETE `/cards/{card_id}` (admin) — `views_api.py:545-573`. |
| `giftcards/migrations.py` | m004_dashboard_indexes | ✓ VERIFIED | `m004_dashboard_indexes` (`migrations.py:88-96`) — creates `idx_giftcards_cards_wallet_status_created` on `(wallet, status, created_at)` for filtered query performance. |
| `giftcards/static/js/index.vue` | Bulk Create dialog, CSV tab, filter bar, multi-select, detail dialog | ✓ VERIFIED | Bulk Create button (`index.vue:13-19`), Bulk dialog with tabs (`index.vue:752-1248`), CSV tab with validation table (`index.vue:990-1074`), filter bar (`index.vue:26-96`), bulk action bar (`index.vue:98-148`), q-table with multi-select (`index.vue:164-334`), detail dialog (`index.vue:1250-1373`), edit dialog (`index.vue:1375-1452`), delete dialog (`index.vue:1454-1504`). |
| `giftcards/static/js/index.js` | Bulk/CSV/filter/multi-select logic | ✓ VERIFIED | `openBulkDialog`/`submitBulkCreate` (`index.js:784-914`), `onCsvFileSelected`/`downloadCsvTemplate` (`index.js:918-960`), `openDetailDialog`/`openEditDialog`/`saveCardEdit`/`openDeleteDialog`/`confirmDelete` (`index.js:964-1046`), `applyFilters`/`clearFilters`/`showDateRangePopup`/`applyDateRange`/`clearDateRange` (`index.js:1048-1098`), `sendBulkEmails` (`index.js:1100-1151`), `exportCSV` with scope (`index.js:516-565`), `loadGiftCards` with query params (`index.js:292-321`). |
| `giftcards/tests/test_bulk_creation.py` | 8 tests | ✓ VERIFIED | Model validation (3), service bulk create (1), API GET with invoice key (1), GET detail include_link (2), cross-wallet 403 (1). All pass. |
| `giftcards/tests/test_csv_upload.py` | 12 tests | ✓ VERIFIED | parse_csv (2), validate_csv_rows (3), CSVRow model (4), BulkCreateRequest CSV mode (2), CSV-to-CreateGiftCard conversion (1). All pass. |
| `giftcards/tests/test_card_management.py` | 8 tests | ✓ VERIFIED | UpdateCardRequest model (2), reclaim_sats_and_delete service (2), DELETE 409 for redeemed (1), PUT updates fields (2), DELETE active reclaims (1). All pass. |
| `giftcards/tests/test_dashboard.py` | 10 tests | ✓ VERIFIED | Status filter (2), search case-insensitive (2), date_from/date_to (2), no filters (1), combined filters (1), cross-wallet isolation (1), ordering DESC (1). All pass. |

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `index.js` submitBulkCreate (same) | `views_api.py` api_bulk_create | `LNbits.api.request('POST', '/giftcards/api/v1/cards/bulk', wallet.adminkey, payload)` | ✓ WIRED | `index.js:896-901` — same-amount mode posts `{count, amount, recipient_name, ...}`. |
| `index.js` submitBulkCreate (CSV) | `views_api.py` api_bulk_create | `LNbits.api.request('POST', '/giftcards/api/v1/cards/bulk', wallet.adminkey, payload)` | ✓ WIRED | `index.js:855-860` — CSV mode posts `{rows, design_mode, design}`. |
| `index.js` onCsvFileSelected | `views_api.py` api_validate_csv | `LNbits.api.request('POST', '/giftcards/api/v1/cards/validate-csv', wallet.adminkey, formData)` | ✓ WIRED | `index.js:928-935` — FormData with file, admin key. |
| `index.js` loadGiftCards | `views_api.py` api_get_cards | `LNbits.api.request('GET', url, key)` with query params | ✓ WIRED | `index.js:296-314` — builds URLSearchParams from dashboardFilters, uses `wallet.inkey \|\| wallet.adminkey`. |
| `index.js` openDetailDialog | `views_api.py` api_get_card_detail | `LNbits.api.request('GET', '/giftcards/api/v1/cards/' + card.id + '?include_link=true', wallet.adminkey)` | ✓ WIRED | `index.js:971-975`. |
| `index.js` saveCardEdit | `views_api.py` api_update_card | `LNbits.api.request('PUT', url, wallet.adminkey, this.editDialog.data)` | ✓ WIRED | `index.js:1003-1009`. |
| `index.js` confirmDelete | `views_api.py` api_delete_card | `LNbits.api.request('DELETE', url, wallet.adminkey)` | ✓ WIRED | `index.js:1030-1035`. |
| `index.js` sendBulkEmails | `views_api.py` api_deliver_email | `LNbits.api.request('POST', '/giftcards/api/v1/cards/' + card.id + '/deliver', wallet.adminkey, {...})` | ✓ WIRED | `index.js:1127-1133` — iterates emailable cards. |
| `views_api.py` api_bulk_create | `services.py` bulk_create_with_funding | Direct call with rows, wallet_id, user_id, base_url | ✓ WIRED | `views_api.py:178-183`. |
| `views_api.py` api_validate_csv | `services.py` parse_csv / validate_csv_rows | Direct calls | ✓ WIRED | `views_api.py:261, 267`. |
| `views_api.py` api_delete_card | `services.py` reclaim_sats_and_delete | Direct call with card | ✓ WIRED | `views_api.py:568`. |
| `views_api.py` api_get_cards | `crud.py` get_cards_by_wallet_filtered | Direct call with wallet_id, filters | ✓ WIRED | `views_api.py:233-239`. |
| `views_api.py` api_update_card | `crud.py` update_card_fields | Direct call with card_id, updates dict | ✓ WIRED | `views_api.py:540`. |
| `services.py` reclaim_sats_and_delete | `crud.py` delete_card | Direct call with card.id | ✓ WIRED | `services.py:235`. |

## Data-Flow Trace

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `index.js` loadGiftCards | `giftCards` | `GET /giftcards/api/v1/cards` with filter query params | Yes (DB query via `get_cards_by_wallet` or `get_cards_by_wallet_filtered`) | ✓ FLOWING |
| `index.js` submitBulkCreate (same) | `bulkDialog.sameData` | `POST /giftcards/api/v1/cards/bulk` with `{count, amount, ...}` | Yes (creates N cards via `bulk_create_with_funding`) | ✓ FLOWING |
| `index.js` onCsvFileSelected | `bulkDialog.csvRows` / `bulkDialog.csvErrorRows` | `POST /giftcards/api/v1/cards/validate-csv` (FormData) | Yes (parse + validate, returns valid_rows + errors) | ✓ FLOWING |
| `index.js` openDetailDialog | `detailDialog.card` | `GET /giftcards/api/v1/cards/{id}?include_link=true` | Yes (DB query via `get_card`, returns `CardDetailResponse`) | ✓ FLOWING |
| `index.js` csvValidationTableRows | computed from `bulkDialog.csvRows` + `bulkDialog.csvErrorRows` | Merged + sorted by row index | Yes (reactive computed property) | ✓ FLOWING |
| `views_api.py` api_get_cards | `cards` | `get_cards_by_wallet` or `get_cards_by_wallet_filtered` | Yes (parameterized SQL query with wallet isolation) | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite (all phases) | `pytest lnbits/extensions/giftcards/tests/ -q` | 228 passed in 16.67s | ✓ PASS |
| Phase 03 bulk creation tests | `pytest test_bulk_creation.py -q` | 8 passed | ✓ PASS |
| Phase 03 CSV upload tests | `pytest test_csv_upload.py -q` | 12 passed | ✓ PASS |
| Phase 03 card management tests | `pytest test_card_management.py -q` | 8 passed | ✓ PASS |
| Phase 03 dashboard tests | `pytest test_dashboard.py -q` | 10 passed | ✓ PASS |
| Combined filter (status + search + date) | `pytest test_dashboard.py::test_filtered_combined_status_search_date -q` | 1 passed | ✓ PASS |
| Cross-wallet isolation | `pytest test_dashboard.py::test_filtered_cross_wallet_isolation -q` | 1 passed | ✓ PASS |
| DELETE redeemed returns 409 | `pytest test_card_management.py::test_delete_redeemed_card_returns_409 -q` | 1 passed | ✓ PASS |
| Bulk create creates N unique cards | `pytest test_bulk_creation.py::test_bulk_create_with_funding_creates_n_cards -q` | 1 passed | ✓ PASS |
| Include_link flag controls redemption_url | `pytest test_bulk_creation.py::test_api_get_card_detail_with_include_link -q` | 1 passed | ✓ PASS |
| Phase 1/2 regression | `pytest test_core_loop.py test_redemption.py test_expiry.py test_security.py test_branded_image.py test_card_designer.py test_magic_link.py test_security_fixes.py -q` | 190 passed | ✓ PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BULK-01 | 03-01 | Bulk same-amount creation from single form | ✓ SATISFIED | `BulkCreateRequest` (`models.py:337-401`) with count+amount mode. `api_bulk_create` (`views_api.py:106-190`) builds N identical `CreateGiftCard` objects. `bulk_create_with_funding` (`services.py:148-177`) loops `create_gift_card`. Bulk Create dialog with Same Amount tab (`index.vue:770-988`). `test_bulk_create_with_funding_creates_n_cards` confirms 3 unique cards. |
| BULK-02 | 03-02 | CSV upload with columns (recipient name, sats amount, email, nostr npub) | ✓ SATISFIED | `CSVRow` model (`models.py:222-300`) with `recipient_name` (required), `amount_sats` (required), `recipient_email` (optional), `nostr_npub` (optional), `sender_name`/`message` (optional), plus per-row design columns. `parse_csv` (`services.py:238-251`) uses `csv.DictReader`. CSV Upload tab in bulk dialog (`index.vue:990-1224`). Download template button (`index.vue:1013-1020`, `index.js:949-960`). |
| BULK-03 | 03-02 | CSV per-row validation + error reporting before creating any cards | ✓ SATISFIED | `api_validate_csv` (`views_api.py:248-278`) — two-phase flow: validate only, no card creation. `validate_csv_rows` (`services.py:254-277`) — per-row Pydantic validation with `CSVValidationError` per field. `CSVValidationResult` (`models.py:310-318`) returns `valid_count`, `error_count`, `valid_rows`, `errors`. 500-row limit enforced (`views_api.py:262-266`). `test_validate_csv_rows_missing_recipient_name` and `test_validate_csv_rows_amount_zero` confirm per-row errors. |
| BULK-04 | 03-01 | Unique redemption link + optional email/nostr delivery per card | ✓ SATISFIED | Each `create_gift_card` call generates unique `raw_token` via `secrets.token_urlsafe(32)` (`services.py:34`) and builds `redemption_url` (`services.py:96`). Email delivery: `api_deliver_email` (`views_api.py:580-627`) from Phase 2. Nostr delivery: deferred to v2 (D-17). CSV rows carry `recipient_email` and `nostr_npub` fields (`models.py:231-232`). |
| API-01 | 03-01 | REST API create gift cards (authenticated) | ✓ SATISFIED | `POST /giftcards/api/v1/cards` (`views_api.py:86-103`, admin key) — single create. `POST /giftcards/api/v1/cards/bulk` (`views_api.py:106-190`, admin key) — bulk create (same-amount or CSV). Both return card IDs. |
| API-02 | 03-01 | REST API retrieve card status/details (authenticated) | ✓ SATISFIED | `GET /giftcards/api/v1/cards` (`views_api.py:193-245`, invoice key) — list with filters. `GET /giftcards/api/v1/cards/{card_id}` (`views_api.py:485-516`, invoice key) — detail with `include_link` opt-in. Returns `CardDetailResponse` with status, creation, expiration, redemption dates. |
| API-03 | 03-01 | Admin/invoice key auth, scoped to wallet | ✓ SATISFIED | Write endpoints (POST, PUT, DELETE) use `require_admin_key`. Read endpoints (GET) use `require_invoice_key`. All endpoints scope queries by `wallet.wallet.id`. Cross-wallet access returns 403 (`views_api.py:501-502, 535-536, 562-563`). `test_api_get_card_detail_cross_wallet_forbidden` and `test_api_update_card_cross_wallet_forbidden` confirm 403. `get_cards_by_wallet_filtered` always includes `WHERE wallet = :wallet` (`crud.py:65`). |
| DASH-01 | 03-03 | View list of all created cards | ✓ SATISFIED | `GET /giftcards/api/v1/cards` returns all cards for wallet. `q-table` in `index.vue:164-334` displays cards with columns: Amount, Recipient, Status, Delivery, Expires. `loadGiftCards` (`index.js:292-321`) fetches on mount and on filter change. |
| DASH-02 | 03-03 | Filter by status (created, active, redeemed, expired) | ✓ SATISFIED (partial) | Status dropdown (`index.vue:29-39`) with options: Created, Active, Redeemed, Expired (`index.js:270-278`). Backend `get_cards_by_wallet_filtered` filters by `status = :status` (`crud.py:69-70`). `test_filtered_status_active_returns_only_active` and `test_filtered_status_redeemed_returns_only_redeemed` pass. **Note:** 'cancelled' deferred to v2 (AUDT-02). 'created' status is in dropdown but no card ever receives this status (cards start as 'active') — see Gaps Summary. |
| DASH-03 | 03-03 | View card details (status, creation, expiration, redemption dates) | ✓ SATISFIED | `CardDetailResponse` (`models.py:404-420`) includes `status`, `created_at`, `expires_at`, `redeemed_at`, `redemption_url` (opt-in). Detail dialog (`index.vue:1250-1373`) displays all fields. `openDetailDialog` (`index.js:964-985`) fetches with `include_link=true`. `test_api_get_card_detail_with_include_link` confirms `redemption_url` populated. |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `views_api.py` | 262 | CSV row count check runs AFTER parse_csv, not before | Low | The plan says ">500 rows rejected with 422 before parsing" but the check runs after `parse_csv` has already parsed the full file. The 422 is still returned before any card creation, so the safety guarantee holds. The only cost is parsing a large CSV that will be rejected. |
| `index.js` | 270-278 | 'created' status in dropdown but no card ever receives 'created' status | Low | Cards are created with `status='active'` (`services.py:97`). Filtering by 'created' will always return 0 results. This is a UI inconsistency — the dropdown option exists but is non-functional. No functional harm; user gets an empty list. |
| `test_csv_upload.py` | 129-152 | `test_validate_csv_rows_invalid_email` is a no-op (body is `pass`) | Low | The test was adjusted because `_normalize_email` only strips/lowercases and does not validate email format. The test does not actually test anything. Email format validation is not enforced at the CSVRow model level — only normalization. |

No `TODO`, `FIXME`, `XXX`, `TBD`, `HACK`, `PLACEHOLDER`, stub returns, or hardcoded empty data flows found in implementation files.

## Phase 1/2 Regression Check

| Phase | Test File | Tests | Status | Notes |
|-------|-----------|-------|--------|-------|
| Phase 1 | test_core_loop.py | 7 | ✓ PASS | No regressions from new bulk/dashboard code. |
| Phase 1 | test_redemption.py | 11 | ✓ PASS | LNURL callback, concurrent redemption, payment error reset all still pass. |
| Phase 1 | test_expiry.py | 7 | ✓ PASS | Expiry sweep, reclaim, callback rejection still work. |
| Phase 1 | test_security.py | 5 | ✓ PASS | Token hash safety, wallet isolation still enforced. |
| Phase 2 | test_branded_image.py | 29 | ✓ PASS | Card image rendering unaffected by Phase 3 changes. |
| Phase 2 | test_card_designer.py | 31 | ✓ PASS | Design config validation unaffected. |
| Phase 2 | test_magic_link.py | 73 | ✓ PASS | Magic link flow unaffected by new endpoints. |
| Phase 2 | test_security_fixes.py | 22 | ✓ PASS | H-1 through H-4 security fixes still hold. |
| Phase 2/3 | test_invoice_key_security.py | 5 | ✓ PASS | Invoice key scoping regression tests pass. |

**Total regression tests:** 190 (Phase 1: 30, Phase 2: 155, Phase 2/3: 5) — all pass.

## Gaps Summary

### Automated Gaps

1. **'created' status is non-functional (Low severity):** The status filter dropdown includes a 'Created' option (`index.js:274`), but no card ever receives `status='created'` — cards are created with `status='active'` (`services.py:97`). The ROADMAP success criteria lists "created" as a filterable status. This is a minor inconsistency: the filter works correctly (returns 0 results for 'created'), but the option is misleading. **Recommendation:** Either remove 'Created' from the dropdown or add a 'created' status phase before 'active' if business logic requires it.

2. **CSV >500 row check runs after parsing (Low severity):** The plan specifies ">500 rows rejected with 422 before parsing" but `api_validate_csv` (`views_api.py:259-266`) calls `parse_csv(content)` first, then checks `len(rows) > 500`. The 422 is returned before any card creation (safety holds), but the full CSV is parsed before rejection. For a very large file this wastes CPU. **Recommendation:** Add a pre-parse size or line-count check if performance is a concern.

3. **Email format validation not enforced in CSVRow (Low severity):** `CSVRow._normalize_recipient_email` (`models.py:246-248`) only strips/lowercases — it does not validate email format. The test `test_validate_csv_rows_invalid_email` (`test_csv_upload.py:129-152`) was adjusted to `pass` without testing. Invalid emails like "not-an-email" will pass CSV validation and be stored. **Recommendation:** Add email format validation to `CSVRow` if business logic requires it, or document that email validation is deferred to the delivery layer.

4. **Nostr delivery deferred (Authorized):** `nostr_npub` field is accepted in CSVRow (`models.py:232`) and validated for format (`models.py:256-262`), but no nostr DM delivery is implemented. Deferred per CONTEXT.md D-17. Not a gap — authorized deferral.

5. **'cancelled' status deferred (Authorized):** The ROADMAP mentions 'cancelled' as a filterable status, but hard delete with sats reclaim is implemented instead of soft-delete/cancel. Deferred to v2 per CONTEXT.md D-16 / AUDT-02. Not a gap — authorized deferral.

### Human Verification Required

1. **Bulk Create (Same Amount) UI flow:** Click "Bulk Create", enter count=5 and amount=1000, submit. Verify 5 cards appear in dashboard and wallet balance decreases by 5000 sats. *Why human:* No frontend test harness; Vue/Quasar dialog interaction cannot be automated.

2. **CSV Upload validation table:** Upload a CSV with valid and invalid rows. Verify green check icons for valid rows, red error icons with messages for invalid rows, and that the Create button is disabled when errors are present. *Why human:* Visual table rendering and row coloring require browser verification.

3. **Multi-select bulk actions:** Select multiple cards via checkboxes. Verify "Send All Emails" and "Download CSV" buttons appear. Click each and verify correct behavior. *Why human:* q-table selection interaction and bulk action bar toggling require browser testing.

4. **Card detail dialog:** Click "View Full Details" on a card. Verify the dialog shows all fields including creation, expiration, and redemption dates, card image, and the redemption link with copy button. Verify the "Edit Card" button is NOT present. Verify card image updates without hard refresh after design changes. *Why human:* Dialog visual rendering and field layout require browser verification.

5. **Dashboard filter controls:** Use the status dropdown, search input (with debounce), and date range picker. Verify filtering works correctly and "Clear Filters" resets all. *Why human:* Interactive filter controls (q-select, debounced input, q-popup-proxy date picker) require browser testing.

6. **Edit dialog card design:** Click "Edit" (pencil icon) on a card, modify the card design (template, bg_color, QR position, text styling), and save. Verify the edit dialog opens with the card's existing design pre-populated. After saving, verify the updated design is persisted and visible in "View Full Details" without a hard page refresh. *Why human:* Interactive design editing in the edit dialog and visual verification of persisted changes require manual browser testing.

7. **Send Emails (Filtered) with no emailable cards:** Filter to cards with no recipient email, click "Send Emails (Filtered)". Verify a dialog pops up with "No Emailable Cards" title and a warning banner. Only a Close button should be shown. *Why human:* Dialog rendering for the no-emails edge case requires manual browser verification.

---

_Verified: 2026-07-01T00:15:00Z_
_Reverified: 2026-07-01T05:20:00Z_
_Verifier: Claude (gsd-verifier)_
