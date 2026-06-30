---
phase: 02-branded-delivery
plan: 01
subsystem: ui
tags: [pillow, pyqrcode, qr, image-rendering, fastapi, vue, quasar, sqlite]

# Dependency graph
requires:
  - phase: 01-core-loop
    provides: GiftCard model, create_gift_card service, make_qr_png, LNURL redemption flow
provides:
  - Branded card image renderer (Pillow compositing with template + QR + text)
  - Migration m003 with design config columns, email columns, and magic_links table
  - DesignConfig, MagicLink, ClaimRequest, DeliverRequest Pydantic v1 models
  - Public card image endpoint (GET /cards/{token_hash}/image)
  - Authenticated printable download endpoint (GET /cards/{card_id}/print)
  - Bundled template PNGs (portrait 425x650, landscape 1050x600)
  - Bundled fonts (DejaVuSans, DejaVuSerif, DejaVuSansMono)
  - Redemption page branded card image display with bare QR fallback
  - Card list Delivery status column with color-coded badges
  - Download PNG button in card list expanded row
affects: [02-branded-delivery, 03-bulk-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.to_thread for CPU-bound Pillow rendering
    - JSON columns for design config (qr_config, text_config)
    - Normalized fraction coordinates for cross-template-dimension positioning
    - Cached font loading via module-level dict
    - fetch+blob download pattern for authenticated file downloads

key-files:
  created:
    - tests/test_branded_image.py
    - static/image/template_portrait.png
    - static/image/template_landscape.png
    - static/fonts/DejaVuSans.ttf
    - static/fonts/DejaVuSerif.ttf
    - static/fonts/DejaVuSansMono.ttf
  modified:
    - migrations.py
    - models.py
    - services.py
    - views_api.py
    - crud.py
    - static/js/redeem.vue
    - static/js/redeem.js
    - static/js/index.vue
    - static/js/index.js
    - tests/test_expiry.py
    - tests/test_security.py
    - tests/test_redemption.py

key-decisions:
  - "Moved make_qr_png from views_api.py to services.py to break circular import between services and views_api"
  - "Used normalized fractions (0.0-1.0) for QR and text positions to work across all template dimensions"
  - "QR size stored as absolute pixels with server-side minimum of 150px enforced via max(150, design.qr_size)"
  - "Design config serialized into two JSON columns (qr_config, text_config) rather than individual columns for simpler group loading"
  - "Asset loading pre-fetched in async wrapper before offloading to thread (get_public_asset is async, Pillow is sync)"

patterns-established:
  - "Pattern: asyncio.to_thread for all Pillow rendering — no blocking calls in async endpoints"
  - "Pattern: JSON TEXT columns for structured config data (qr_config, text_config) parsed with json.loads and DesignConfig fallback"
  - "Pattern: fetch+blob download for authenticated file downloads (admin key in X-Api-Key header)"
  - "Pattern: v-if conditional rendering for branded vs bare QR fallback on redemption page"

requirements-completed:
  - TPLT-01
  - TPLT-03
  - DELV-04

coverage:
  - id: D1
    description: "Migration m003 with design config columns, email columns, and magic_links table"
    requirement: "TPLT-01"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_m003_migration_exists_and_is_async"
        status: pass
    human_judgment: false
  - id: D2
    description: "DesignConfig, MagicLink, ClaimRequest, DeliverRequest Pydantic v1 models with correct defaults"
    requirement: "TPLT-01"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_design_config_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_new_models_importable"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_create_gift_card_accepts_design_and_email"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_gift_card_has_email_status"
        status: pass
    human_judgment: false
  - id: D3
    description: "Bundled template PNGs (portrait 425x650, landscape 1050x600) and font TTFs"
    requirement: "TPLT-01"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_template_portrait_dimensions"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_template_landscape_dimensions"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_bundled_fonts_exist"
        status: pass
    human_judgment: false
  - id: D4
    description: "Card image renderer with Pillow compositing (template + QR + text) via asyncio.to_thread"
    requirement: "TPLT-03"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_get_font_returns_non_none"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_get_font_caches"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_render_card_image_is_async"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_render_card_image_returns_png_bytes"
        status: pass
    human_judgment: false
  - id: D5
    description: "Public card image endpoint and authenticated printable download endpoint"
    requirement: "DELV-04"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_image_endpoint_registered"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_print_endpoint_registered"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_image_endpoint_is_public"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_print_endpoint_is_authenticated"
        status: pass
    human_judgment: false
  - id: D6
    description: "Create endpoint accepts design config, public endpoint returns has_design field"
    requirement: "TPLT-01"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_create_gift_card_handles_design_config"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_public_card_endpoint_returns_has_design"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_public_card_endpoint_has_design_true"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_public_card_endpoint_has_design_false"
        status: pass
    human_judgment: false
  - id: D7
    description: "Redemption page shows branded card image when design config exists, bare QR fallback otherwise"
    requirement: "TPLT-03"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_redeem_vue_has_branded_card_img"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_redeem_js_has_card_image_url"
        status: pass
    human_judgment: true
    rationale: "Visual rendering of branded card image on redemption page requires manual browser verification"
  - id: D8
    description: "Card list Delivery status column with color-coded badges and Download PNG button"
    requirement: "DELV-04"
    verification:
      - kind: unit
        ref: "tests/test_branded_image.py#test_index_js_has_delivery_and_download"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_index_vue_has_download_png"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_get_delivery_status_color_mapping"
        status: pass
      - kind: unit
        ref: "tests/test_branded_image.py#test_get_delivery_status_text_mapping"
        status: pass
    human_judgment: true
    rationale: "Card list UI rendering with Delivery column and Download PNG button requires manual browser verification"

# Metrics
duration: 25min
completed: 2026-06-30
status: complete
---

# Phase 2 Plan 01: Branded Card Image Pipeline Summary

**Pillow-based branded card image renderer with template + QR + text compositing, public image endpoint, authenticated printable download, and redemption page UI integration**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-30T03:50:00Z
- **Completed:** 2026-06-30T04:15:00Z
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments
- Migration m003 adds 9 design/email columns to cards table and creates magic_links table with indexes
- Card image renderer composites template + QR + text via Pillow, offloaded with asyncio.to_thread()
- Public image endpoint serves branded card PNGs by token_hash (no auth required)
- Authenticated print endpoint returns 3x-resolution PNG with Content-Disposition attachment header
- Redemption page shows branded card image when design config exists, falls back to bare QR for Phase 1 cards
- Card list gains Delivery status column with color-coded badges (not_sent/sent/failed) and em-dash for no-email cards
- Download PNG button in expanded row triggers authenticated blob download of printable card image
- All 59 tests pass (30 existing + 29 new) — full backward compatibility maintained

## Task Commits

Each task was committed atomically using TDD (RED → GREEN):

1. **Task 1: Migration m003, extended models, and bundled assets**
   - `94634f1` (test): failing tests for models, migration, and assets
   - `25beae3` (feat): migration m003, DesignConfig/MagicLink/ClaimRequest/DeliverRequest models, bundled templates and fonts
2. **Task 2: Card image renderer service and render/print endpoints**
   - `6369ca4` (test): failing tests for renderer and endpoints
   - `8380771` (feat): get_font, _render_card_image_sync, render_card_image, image/print endpoints, crud updates
3. **Task 3: Extend create endpoint, redemption page, card list, and tests**
   - `190e37a` (test): failing tests for create endpoint, public has_design, and UI
   - `d801d84` (feat): create_gift_card design serialization, has_design field, branded card image UI, delivery column

## Files Created/Modified
- `migrations.py` - m003_branded_delivery migration (9 card columns + magic_links table)
- `models.py` - DesignConfig, MagicLink, ClaimRequest, DeliverRequest models; extended GiftCard, CreateGiftCard, GiftCardSummary, PublicGiftCard
- `services.py` - make_qr_png (moved from views_api), get_font, _parse_design_config, _render_card_image_sync, render_card_image; create_gift_card extended with design serialization
- `views_api.py` - api_card_image (public), api_card_print (authenticated); api_get_public_card extended with has_design
- `crud.py` - update_card_email_status; get_cards_by_wallet extended with email columns
- `static/image/template_portrait.png` - Bundled portrait template (425x650)
- `static/image/template_landscape.png` - Bundled landscape template (1050x600)
- `static/fonts/DejaVuSans.ttf`, `DejaVuSerif.ttf`, `DejaVuSansMono.ttf` - Bundled fonts for text rendering
- `static/js/redeem.vue` - Branded card image element with v-if conditional and CSS
- `static/js/redeem.js` - cardImageUrl computed property
- `static/js/index.vue` - Delivery column rendering and Download PNG button
- `static/js/index.js` - Delivery column, getDeliveryStatusColor/Text, downloadPrintable method
- `tests/test_branded_image.py` - 29 tests covering models, migration, assets, renderer, endpoints, and UI
- `tests/test_expiry.py`, `tests/test_security.py`, `tests/test_redemption.py` - Updated to run m003 migration

## Decisions Made
- Moved `make_qr_png` from `views_api.py` to `services.py` to break a circular import that arose when `services.py` needed `make_qr_png` for the renderer and `views_api.py` needed `render_card_image` from `services.py`
- Used normalized fractions (0.0–1.0) for QR and text positions per RESEARCH.md §1 recommendation — works across all template dimensions without recalculation
- QR size stored as absolute pixels with server-side minimum of 150px enforced via `max(150, design.qr_size) * scale`
- Design config serialized into two JSON TEXT columns (`qr_config`, `text_config`) rather than individual columns — simpler group loading and passing to renderer
- Asset loading pre-fetched in the async `render_card_image` wrapper before offloading to thread, since `get_public_asset` is async but Pillow compositing is sync

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Circular import between services.py and views_api.py**
- **Found during:** Task 2 (renderer implementation)
- **Issue:** `services.py` imported `make_qr_png` from `views_api.py` while `views_api.py` imported `render_card_image` from `services.py`, causing a circular import
- **Fix:** Moved `make_qr_png` function from `views_api.py` to `services.py` and updated `views_api.py` to import it from `services.py`
- **Files modified:** services.py, views_api.py
- **Verification:** All imports succeed, all 59 tests pass
- **Committed in:** 8380771 (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Existing test fixtures missing m003 migration**
- **Found during:** Task 1 (migration implementation)
- **Issue:** Existing tests in test_expiry.py, test_security.py, test_redemption.py manually call m001 and m002 but not m003, causing INSERT failures when the GiftCard model includes new columns
- **Fix:** Added `m003_branded_delivery(db)` call to `_reset_table()` in all three test files
- **Files modified:** tests/test_expiry.py, tests/test_security.py, tests/test_redemption.py
- **Verification:** All 30 existing tests pass with m003 migration
- **Committed in:** 25beae3 (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness and test compatibility. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. Bundled templates and fonts are included in the extension.

## Next Phase Readiness
- Branded card image renderer is complete and tested — Plans 02-02 (card designer UI) and 02-03 (magic link + email) can build on this foundation
- Migration m003 provides the schema for all Phase 2 features (design config, email delivery, magic links)
- The `render_card_image` function and image/print endpoints are ready for the card designer's final render and the email delivery flow
- The `MagicLink` model and `magic_links` table are in place for Plan 02-03's magic link verification flow

## Self-Check: PASSED

- All 29 tests in `test_branded_image.py` pass
- All 59 tests in the full test suite pass (30 existing + 29 new)
- All acceptance criteria for all 3 tasks verified individually
- Plan-level verification: `pytest giftcards/tests/test_branded_image.py -x` passes
- Backward compatibility: `pytest giftcards/tests/ -x` passes (all Phase 1 tests green)

---
*Phase: 02-branded-delivery*
*Completed: 2026-06-30*
