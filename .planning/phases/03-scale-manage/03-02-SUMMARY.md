---
phase: 03-scale-manage
plan: 02
subsystem: api
tags: [csv, pydantic, fastapi, vue, quasar, crud]

# Dependency graph
requires:
  - phase: 03-01
    provides: bulk_create_with_funding, delete_card, update_card_fields CRUD functions, BulkCreateRequest model
provides:
  - CSV bulk upload with per-row validation (parse_csv, validate_csv_rows)
  - CSVRow and CSVValidationResult Pydantic models
  - POST /cards/validate-csv endpoint (two-phase validate-then-create)
  - CSV mode in POST /cards/bulk (rows + design_mode)
  - PUT /cards/{card_id} endpoint for card metadata editing
  - DELETE /cards/{card_id} endpoint with sats reclaim and 409 guard
  - reclaim_sats_and_delete service (active→reclaim+delete, expired→delete only)
  - Frontend CSV Upload tab with validation table, edit dialog, delete dialog
affects: [03-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-phase CSV flow: validate-csv endpoint returns per-row results, then bulk create with validated rows"
    - "Root validator on BulkCreateRequest for mode switching (same-amount vs CSV)"
    - "Bech32 npub regex validation on CSVRow model"
    - "Sats reclaim on delete: active cards credit issuer wallet, expired cards skip reclaim"

key-files:
  created:
    - tests/test_csv_upload.py
    - tests/test_card_management.py
  modified:
    - models.py
    - services.py
    - views_api.py
    - static/js/index.vue
    - static/js/index.js

key-decisions:
  - "CSVRow placed before BulkCreateRequest in models.py to resolve forward reference for Optional[List[CSVRow]] field"
  - "validate-csv route defined before /{card_id} routes to avoid FastAPI path conflicts"
  - "Email format validation is normalization-only (strip/lowercase), not RFC validation — consistent with existing _normalize_email pattern"
  - "UpdateCardRequest has no amount field — D-15 requirement, enforced by model schema"

patterns-established:
  - "Two-phase CSV: validate first (POST /validate-csv), create second (POST /bulk with rows)"
  - "Per-row validation with CSVValidationError list — no partial create on error"
  - "reclaim_sats_and_delete: status-based reclaim logic (active=reclaim, expired=skip, redeemed=caller rejects)"

requirements-completed:
  - BULK-02
  - BULK-03

coverage:
  - id: D1
    description: "CSV parse and validate: parse_csv strips BOM, validate_csv_rows produces per-row errors"
    requirement: "BULK-02"
    verification:
      - kind: unit
        ref: "tests/test_csv_upload.py#test_parse_csv_valid_returns_dicts_with_row_num"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_parse_csv_strips_bom"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_validate_csv_rows_all_valid"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_validate_csv_rows_missing_recipient_name"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_validate_csv_rows_amount_zero"
        status: pass
    human_judgment: false
  - id: D2
    description: "CSVRow model with nostr_npub bech32 validation and BulkCreateRequest CSV mode"
    requirement: "BULK-02"
    verification:
      - kind: unit
        ref: "tests/test_csv_upload.py#test_csv_row_all_optional_omitted"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_csv_row_nostr_npub_invalid_format"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_csv_row_nostr_npub_none_passes"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_csv_row_nostr_npub_valid_format"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_bulk_create_request_csv_mode_valid"
        status: pass
      - kind: unit
        ref: "tests/test_csv_upload.py#test_bulk_create_request_csv_mode_converts_to_create_gift_card"
        status: pass
    human_judgment: false
  - id: D3
    description: "Card management: UpdateCardRequest (no amount), reclaim_sats_and_delete, PUT/DELETE endpoints with 409 guard"
    requirement: "BULK-03"
    verification:
      - kind: unit
        ref: "tests/test_card_management.py#test_update_card_request_valid"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_update_card_request_no_amount_field"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_reclaim_sats_and_delete_active_card"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_reclaim_sats_and_delete_expired_card"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_delete_redeemed_card_returns_409"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_api_update_card_updates_fields"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_api_update_card_cross_wallet_forbidden"
        status: pass
      - kind: unit
        ref: "tests/test_card_management.py#test_api_delete_card_active_reclaims_and_deletes"
        status: pass
    human_judgment: false
  - id: D4
    description: "Frontend CSV Upload tab with validation table, card edit dialog, card delete dialog"
    requirement: "BULK-02"
    verification: []
    human_judgment: true
    rationale: "UI components require manual verification — no frontend test framework configured for Vue/Quasar components"

# Metrics
duration: 35min
completed: 2025-07-17
status: complete
---

# Phase 03 Plan 02: CSV Bulk Upload & Card Management Summary

**CSV bulk upload with per-row validation, card metadata editing (PUT), and card deletion with sats reclaim (DELETE)**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)
- **Tests:** 20 new (12 CSV + 8 card management), 218 total passing

## Accomplishments
- CSV bulk upload with two-phase flow: validate-csv endpoint returns per-row validation table, then bulk create with validated rows
- Card metadata editing via PUT endpoint (recipient_name, sender_name, message, recipient_email — amount not editable)
- Card deletion via DELETE endpoint with sats reclaim (active cards credit issuer wallet, expired cards skip reclaim, redeemed cards return 409)
- Frontend CSV Upload tab with file picker, validation table (green/red rows), design mode selector, and template download
- Frontend card detail, edit, and delete dialogs with status-aware UI

## Task Commits

Each task was committed atomically:

1. **Task 1: TDD RED — Failing tests** — `7c09db5` (test)
2. **Task 2: Backend GREEN — Models, services, endpoints** — `d68b498` (feat)
3. **Task 3: Frontend — CSV tab, edit/delete dialogs** — `eff438e` (feat)

## Files Created/Modified
- `tests/test_csv_upload.py` - 12 tests for parse_csv, validate_csv_rows, CSVRow model, BulkCreateRequest CSV mode
- `tests/test_card_management.py` - 8 tests for UpdateCardRequest, reclaim_sats_and_delete, PUT/DELETE endpoints
- `models.py` - CSVRow, CSVValidationError, CSVValidationResult, UpdateCardRequest models; BulkCreateRequest extended with rows/design_mode/root_validator
- `services.py` - parse_csv, validate_csv_rows, reclaim_sats_and_delete functions
- `views_api.py` - api_validate_csv, api_update_card, api_delete_card endpoints; api_bulk_create extended for CSV mode
- `static/js/index.vue` - CSV Upload tab, card detail/edit/delete dialogs, edit/delete action buttons
- `static/js/index.js` - CSV upload logic, edit/delete methods, computed properties for CSV validation table

## Decisions Made
- CSVRow placed before BulkCreateRequest in models.py to resolve forward reference for `Optional[List[CSVRow]]` field
- validate-csv route defined before `/{card_id}` routes to avoid FastAPI path conflicts
- Email format validation is normalization-only (strip/lowercase), not RFC validation — consistent with existing `_normalize_email` pattern
- UpdateCardRequest has no amount field — D-15 requirement, enforced by model schema

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Initial test for `test_bulk_create_request_csv_mode_converts_to_create_gift_card` failed because `create_gift_card` is called with keyword arguments, not positional. Fixed by checking both `c.args` and `c.kwargs` in the mock assertion.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | `7c09db5` (test) | ✓ Tests skip due to missing imports |
| GREEN | `d68b498` (feat) | ✓ All 20 tests pass |
| REFACTOR | N/A | — No refactor needed |

## Next Phase Readiness
- CSV bulk upload and card management complete
- Plan 03-03 (filtering, search, pagination) can proceed
- All 218 tests pass with no regressions

---
*Phase: 03-scale-manage*
*Completed: 2025-07-17*
