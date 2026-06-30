---
phase: 03-scale-manage
plan: 03
subsystem: api
tags: [fastapi, pydantic-v1, quasar, vue3, server-side-filtering, multi-select, bulk-actions, csv-export]

# Dependency graph
requires:
  - phase: 03-01
    provides: api_get_cards filter query params, require_invoice_key reads, m004 index
  - phase: 03-02
    provides: card detail/edit/delete dialogs, View Full Details button, openDetailDialog/openEditDialog/confirmDelete methods
provides:
  - get_cards_by_wallet_filtered CRUD with server-side filtering (status, search, date range)
  - api_get_cards wired to filtered query when any filter param is present
  - Dashboard filter bar UI (status dropdown, search input, date range picker)
  - Multi-select q-table with bulk action bar (Send All Emails, Download CSV)
  - Card detail dialog with branded image preview
  - CSV export with scope parameter (selected/filtered/all)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Server-Side Filtered Query: dynamic WHERE clause with parameterized SQL, always-present wallet isolation, LOWER(col) LIKE LOWER(:search) for cross-DB case-insensitivity"
    - "Date string to timestamp conversion: datetime.fromisoformat handles both date-only and full datetime strings"
    - "Query object normalization: direct test calls to FastAPI endpoints receive Query objects, not resolved defaults"

key-files:
  created:
    - tests/test_dashboard.py
  modified:
    - crud.py
    - views_api.py
    - static/js/index.vue
    - static/js/index.js

key-decisions:
  - "statusFilterOptions excludes 'cancelled' since no Phase 3 operation produces it (deferred to v2 AUDT-02)"
  - "openDetailDialog fetches GET /cards/{id}?include_link=true with admin key for full details including redemption_url"
  - "Card image preview uses the public /cards/{token_hash}/image endpoint (no auth needed)"
  - "loadGiftCards uses invoice key (inkey) since GET now accepts invoice key (D-10)"
  - "Query object normalization added to api_get_cards so direct test calls (Query objects) work alongside real FastAPI requests"

patterns-established:
  - "Server-Side Filtered Query pattern: dynamic WHERE with parameterized values, LOWER() LIKE LOWER() for cross-DB search, db.timestamp_placeholder for dates"
  - "Bulk action pattern: iterate existing per-card endpoint (POST /deliver) with ownership check per card (T-03-16)"
  - "CSV export scope pattern: exportCSV(scope) accepts 'selected'/'filtered'/undefined for targeted or full export"

requirements-completed:
  - DASH-01
  - DASH-02
  - DASH-03

# Coverage metadata
coverage:
  - id: D1
    description: "Server-side filtered query: get_cards_by_wallet_filtered with status, search, date range, cross-wallet isolation"
    requirement: "DASH-02"
    verification:
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_status_active_returns_only_active"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_search_case_insensitive_recipient"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_date_from_returns_cards_after_date"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_date_to_returns_cards_before_date"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_combined_status_search_date"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_cross_wallet_isolation"
        status: pass
      - kind: unit
        ref: "tests/test_dashboard.py#test_filtered_results_ordered_by_created_at_desc"
        status: pass
    human_judgment: false
  - id: D2
    description: "Dashboard filter bar, multi-select bulk actions, card detail dialog with image, CSV export scope"
    requirement: "DASH-01"
    verification: []
    human_judgment: true
    rationale: "UI components require manual verification — no frontend test framework configured for Vue/Quasar components"

# Metrics
duration: 22min
completed: 2026-06-30
status: complete
---

# Phase 03 Plan 03: Dashboard Management Console Summary

**Server-side filtered card queries with status/search/date filters, multi-select bulk actions (Send All Emails, Download CSV), card detail dialog with branded image preview, and scoped CSV export**

## Performance

- **Duration:** ~22 min
- **Tasks:** 3
- **Files modified:** 5 (1 created, 4 modified)
- **Tests:** 10 new (dashboard filtering), 228 total passing

## Accomplishments
- get_cards_by_wallet_filtered CRUD with dynamic WHERE clause, parameterized SQL (T-03-14), always-present wallet isolation (T-03-15), LOWER(col) LIKE LOWER(:search) for cross-DB case-insensitive search (Pitfall 3), db.timestamp_placeholder for dates, ORDER BY created_at DESC
- api_get_cards wired to filtered query when any filter param is present; date strings converted to timestamps via _parse_date_to_timestamp
- Dashboard filter bar: q-select status (clearable, no 'cancelled'), q-input search (debounce=300), q-date range popup, Clear Filters button
- Multi-select q-table with bulk action bar: Send All Emails + Download CSV for selected cards, Send All (Filtered) + Download CSV (Filtered) when none selected
- Card detail dialog enhanced with branded image preview (public /cards/{token_hash}/image endpoint)
- CSV export extended with scope parameter ('selected', 'filtered', undefined) and expanded column set
- sendBulkEmails(scope) iterates POST /cards/{id}/deliver per card with ownership check (T-03-16)

## Task Commits

Each task was committed atomically:

1. **Task 1: TDD RED — Failing tests** — `b3539ce` (test)
2. **Task 2: Backend GREEN — get_cards_by_wallet_filtered + api_get_cards wiring** — `546e427` (feat)
3. **Task 3: Frontend — Filter bar, multi-select, detail dialog, CSV export** — `ff23a1a` (feat)

_Note: TDD tasks have RED (test) → GREEN (feat) commits._

## Files Created/Modified
- `tests/test_dashboard.py` - 10 test functions covering status, search, date_from, date_to, no-filter, combined filters, cross-wallet isolation, ORDER BY
- `crud.py` - get_cards_by_wallet_filtered with dynamic WHERE, parameterized SQL, LOWER() LIKE LOWER() search, timestamp_placeholder dates
- `views_api.py` - api_get_cards delegates to get_cards_by_wallet_filtered when filters present; _parse_date_to_timestamp helper; Query object normalization
- `static/js/index.vue` - Filter bar, bulk action bar, q-table selection=multiple, detail dialog card image preview
- `static/js/index.js` - dashboardFilters data, selectedCards, statusFilterOptions/anyFilterActive computed, applyFilters/clearFilters/showDateRangePopup/applyDateRange/clearDateRange/sendBulkEmails methods, loadGiftCards with query string + invoice key, exportCSV with scope, openDetailDialog with full detail fetch

## Decisions Made
- statusFilterOptions excludes 'cancelled' since no Phase 3 operation produces it (deferred to v2 AUDT-02 soft-delete/cancel)
- openDetailDialog fetches GET /cards/{id}?include_link=true with admin key for full details including redemption_url
- Card image preview uses the public /cards/{token_hash}/image endpoint (no auth needed)
- loadGiftCards uses invoice key (inkey) since GET now accepts invoice key (D-10)
- Query object normalization added to api_get_cards so direct test calls (Query objects) work alongside real FastAPI requests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Query object normalization in api_get_cards**
- **Found during:** Task 2 (Backend implementation)
- **Issue:** When api_get_cards is called directly in unit tests (not through FastAPI), the Query(None) default params are Query objects, not None. The has_filters check saw them as not-None, causing get_cards_by_wallet_filtered to receive Query objects and fail with "object of type 'Query' has no len()"
- **Fix:** Added normalization at the top of api_get_cards: if status/search is not None and not a str, set to None; if date_from/date_to is not None and not a str, skip timestamp conversion
- **Files modified:** views_api.py
- **Verification:** All 228 tests pass including the pre-existing test_api_get_cards_with_invoice_key
- **Committed in:** 546e427 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Auto-fix necessary for test compatibility. No scope creep.

## Issues Encountered
None

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | `b3539ce` (test) | ✓ 10 tests fail with ImportError |
| GREEN | `546e427` (feat) | ✓ All 10 tests pass |
| REFACTOR | N/A | — No refactor needed |

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Dashboard management console complete with filtering, multi-select, bulk actions, and detail views
- All 228 tests pass with no regressions
- Phase 03 (Scale & Manage) is fully complete across all 3 plans

---
*Phase: 03-scale-manage*
*Completed: 2026-06-30*
