---
phase: 03-scale-manage
plan: 01
subsystem: api
tags: [fastapi, pydantic-v1, quasar, vue3, bulk-creation, invoice-key, rest-api]

# Dependency graph
requires:
  - phase: 02-branded-delivery
    provides: DesignConfig model, card designer UI, email delivery infrastructure
provides:
  - BulkCreateRequest model for same-amount bulk card creation
  - CardDetailResponse model with optional redemption_url (include_link flag)
  - bulk_create_with_funding service (loops create_gift_card)
  - POST /cards/bulk endpoint (admin key)
  - GET /cards/{card_id} endpoint (invoice key, include_link opt-in)
  - GET /cards switched to invoice key + filter query params
  - delete_card and update_card_fields CRUD functions (for Plan 02/03)
  - m004_dashboard_indexes migration
  - Bulk Create button + dialog UI (Same Amount tab)
affects: [03-02-csv-bulk, 03-03-dashboard-management]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mixed auth: require_admin_key for writes, require_invoice_key for reads (events extension pattern)"
    - "Bulk creation reuses create_gift_card as inner loop (no batched insert)"
    - "include_link query flag for opt-in redemption_url exposure"

key-files:
  created:
    - tests/test_bulk_creation.py
  modified:
    - models.py
    - services.py
    - crud.py
    - views_api.py
    - migrations.py
    - static/js/index.vue
    - static/js/index.js

key-decisions:
  - "BulkCreateRequest uses Field(gt=0, le=500) for count + @validator backup (D-08)"
  - "CardDetailResponse defaults redemption_url to None; only populated when include_link=true (D-11)"
  - "bulk_create_with_funding is all-or-nothing — re-raises on any create_gift_card failure (D-07)"
  - "GET /cards/{card_id} placed after /{token_hash}/image and /{card_id}/print to avoid path conflicts"
  - "Filter query params (status, search, date_from, date_to) accepted on api_get_cards but filtering logic deferred to Plan 03"

patterns-established:
  - "Mixed-auth pattern: require_invoice_key for reads, require_admin_key for writes"
  - "Bulk service pattern: loop existing single-item service function, collect responses, re-raise on failure"
  - "Opt-in sensitive field pattern: query flag controls whether redemption_url is included in response"

requirements-completed:
  - BULK-01
  - BULK-04
  - API-01
  - API-02
  - API-03

# Coverage metadata
coverage:
  - id: D1
    description: "Bulk same-amount gift card creation via POST /cards/bulk with BulkCreateRequest model"
    requirement: "BULK-01"
    verification:
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_bulk_create_request_valid"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_bulk_create_request_count_zero_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_bulk_create_request_count_over_500_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_bulk_create_with_funding_creates_n_cards"
        status: pass
    human_judgment: false
  - id: D2
    description: "Invoice-key read endpoints with include_link opt-in flag for redemption_url"
    requirement: "API-02"
    verification:
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_api_get_cards_with_invoice_key"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_api_get_card_detail_without_include_link"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_api_get_card_detail_with_include_link"
        status: pass
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_api_get_card_detail_cross_wallet_forbidden"
        status: pass
    human_judgment: false
  - id: D3
    description: "Bulk Create button + dialog UI with Same Amount tab and design mode selector"
    requirement: "BULK-01"
    verification:
      - kind: automated_ui
        ref: "static/js/index.vue#Bulk Create button + dialog"
        status: pass
    human_judgment: true
    rationale: "Frontend UI rendering cannot be verified by automated tests in this stack (no browser test harness); verified by acceptance criteria grep checks and existing test suite regression."
  - id: D4
    description: "Admin key for writes, invoice key for reads (API-03 auth scoping)"
    requirement: "API-03"
    verification:
      - kind: unit
        ref: "tests/test_bulk_creation.py#test_api_get_card_detail_cross_wallet_forbidden"
        status: pass
    human_judgment: false

# Metrics
duration: 18min
completed: 2026-07-01
status: complete
---

# Phase 03 Plan 01: Bulk Creation & Invoice-Key API Summary

**Bulk same-amount gift card creation (POST /cards/bulk) with invoice-key read endpoints and include_link opt-in flag for redemption_url**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-01T00:00:00Z
- **Completed:** 2026-07-01T00:18:00Z
- **Tasks:** 3
- **Files modified:** 7 (5 backend + 2 frontend + 1 test)

## Accomplishments
- BulkCreateRequest model with count validation (gt=0, le=500) and amount validation (gt=0)
- bulk_create_with_funding service that loops create_gift_card (all-or-nothing, unique tokens per card)
- POST /cards/bulk endpoint requiring admin key, returns {created, card_ids}
- GET /cards switched from require_admin_key to require_invoice_key (D-10) with filter query params accepted
- GET /cards/{card_id} endpoint with include_link opt-in flag (D-11) and ownership check (403)
- CardDetailResponse model with redemption_url defaulting to None
- delete_card and update_card_fields CRUD functions (for Plan 02/03 endpoints)
- m004_dashboard_indexes migration (wallet, status, created_at composite index)
- Bulk Create button + dialog UI with Same Amount tab, design mode selector (none/shared), balance warning

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests (RED)** - `6a8b5a0` (test)
2. **Task 2: Backend implementation (GREEN)** - `74c1c01` (feat)
3. **Task 3: Frontend Bulk Create dialog** - `a829b0e` (feat)

_Note: TDD tasks have RED (test) → GREEN (feat) commits._

## Files Created/Modified
- `tests/test_bulk_creation.py` - 8 test functions covering model validation, service, and API endpoint behaviors
- `models.py` - BulkCreateRequest (count/amount validators) + CardDetailResponse (redemption_url opt-in)
- `services.py` - bulk_create_with_funding (loops create_gift_card, all-or-nothing)
- `crud.py` - delete_card + update_card_fields (editable fields allowlist)
- `views_api.py` - POST /bulk (admin key), GET /{card_id} (invoice key, include_link), api_get_cards → invoice key + filter params
- `migrations.py` - m004_dashboard_indexes (composite index for dashboard filter performance)
- `static/js/index.vue` - Bulk Create button + dialog with q-tabs (Same Amount + CSV placeholder), card designer reuse
- `static/js/index.js` - bulkDialog data, openBulkDialog/submitBulkCreate methods, computed helpers, 'created' status handling

## Decisions Made
- Placed GET /{card_id} endpoint after /{token_hash}/image and /{card_id}/print routes to avoid FastAPI path conflicts
- Filter query params (status, search, date_from, date_to) added to api_get_cards signature but filtering logic deferred to Plan 03 (per plan action step 11)
- CSV tab is a placeholder ("CSV upload available in next update") — Plan 02 implements the full CSV flow
- 'cancelled' status NOT added to getStatusColor/getStatusText since no Phase 3 operation produces it (deferred to v2 AUDT-02)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Bulk same-amount creation is complete and tested
- Invoice-key read endpoints are ready for external system integration
- Plan 02 can extend BulkCreateRequest with optional `rows` and `design_mode` fields for CSV mode
- Plan 02 can extend api_bulk_create to handle CSV mode (when data.rows is present)
- Plan 03 can implement the filtering logic for the query params already accepted by api_get_cards
- delete_card and update_card_fields CRUD functions are ready for Plan 02/03 delete and edit endpoints

---
*Phase: 03-scale-manage*
*Completed: 2026-07-01*
