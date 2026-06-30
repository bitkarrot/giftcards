---
phase: 02-branded-delivery
plan: 02
subsystem: ui
tags: [vue, quasar, drag-and-drop, pointer-events, qr, image-rendering, asset-upload]

# Dependency graph
requires:
  - phase: 02-branded-delivery
    provides: Branded card image renderer, DesignConfig model, migration m003, bundled templates and fonts, image/print endpoints
provides:
  - Interactive card designer in create dialog with template selection, drag-to-place QR + text, QR resize handle, and text styling controls
  - Design config serialization (normalized fractions) sent with card creation request
  - Custom template upload via LNBits asset system with client-side dimension validation (D-03)
  - Client-side QR minimum size enforcement (150px) in resize handler
  - Test suite covering card designer UI strings, JS methods, and DesignConfig model behavior
affects: [02-branded-delivery, 03-bulk-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Native HTML5 pointer events for drag-and-drop (no external library)
    - setPointerCapture for reliable drag tracking outside element bounds
    - Normalized fraction coordinates (0.0-1.0) for cross-template-dimension positioning
    - FormData POST to /api/v1/assets?public_asset=true for custom template upload
    - Client-side image dimension validation via img.naturalWidth/naturalHeight (D-03)
    - Reactive state binding for live preview (qrX/qrY/textX/textY bound to :style)

key-files:
  created:
    - tests/test_card_designer.py
  modified:
    - static/js/index.vue
    - static/js/index.js

key-decisions:
  - "Used native HTML5 pointer events (pointerdown/pointermove/pointerup) with setPointerCapture instead of an external drag library — matches LNBits frontend stack (no build step, no extra deps)"
  - "QR size stored as absolute pixels with client-side minimum of 150px enforced via Math.max(minQrSize, newSize) in onResize — defense in depth with server-side clamping from Plan 02-01"
  - "Preview dimensions: portrait 212x325px (half of 425x650), landscape 262x150px (quarter-scale of 1050x600) — scaled to fit dialog while preserving aspect ratio"
  - "D-03 advisory fix: added client-side dimension validation in handleTemplateSelected — reads img.naturalWidth/naturalHeight, rejects images > 1500x2000px before upload"
  - "Font family mapped to CSS generic families (sans-serif/serif/monospace) for preview; server-side renderer uses actual DejaVu TTF files"

patterns-established:
  - "Pattern: Native pointer events with setPointerCapture for drag-and-drop in Vue/Quasar (no library needed)"
  - "Pattern: Client-side dimension validation before asset upload (naturalWidth/naturalHeight check)"
  - "Pattern: Reactive :style binding for live preview positioning (qrX/qrY/qrSize → left/top/width/height)"
  - "Pattern: Design config serialization with normalized fractions computed from preview pixel coordinates"

requirements-completed:
  - TPLT-02

# Coverage metadata
coverage:
  - id: D1
    description: "Card designer section in create dialog with template selection, drag preview, QR resize handle, and text styling controls"
    requirement: "TPLT-02"
    verification:
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_card_preview"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_draggable_qr"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_resize_handle"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_draggable_text"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_card_design_heading"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_vue_has_hidden_file_input"
        status: pass
    human_judgment: true
    rationale: "Interactive drag, resize, and styling controls require manual browser verification to confirm UX behavior"
  - id: D2
    description: "Drag interaction logic (startDrag, onDrag, endDrag, startResize, onResize) with pointer capture and bounds clamping"
    requirement: "TPLT-02"
    verification:
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_start_drag"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_on_drag"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_end_drag"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_start_resize"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_on_resize"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_start_drag_uses_pointer_capture"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_on_resize_enforces_min"
        status: pass
    human_judgment: true
    rationale: "Pointer event drag behavior requires manual browser verification to confirm smooth interaction"
  - id: D3
    description: "Template upload logic (uploadAssetFile, triggerTemplateUpload, handleTemplateSelected) with D-03 dimension validation"
    requirement: "TPLT-02"
    verification:
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_upload_asset_file"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_handle_template_selected"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_trigger_template_upload"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_upload_uses_form_data_and_public_asset"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_dimension_validation"
        status: pass
    human_judgment: true
    rationale: "File upload and dimension validation flow requires manual browser verification"
  - id: D4
    description: "Design config serialization with normalized fractions sent to create endpoint"
    requirement: "TPLT-02"
    verification:
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_qr_x_frac_serialization"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_font_color_serialization"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_design_data_properties"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_has_on_template_change"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_js_reset_create_dialog_resets_design"
        status: pass
    human_judgment: false
  - id: D5
    description: "DesignConfig model behavior and backward compatibility tests"
    requirement: "TPLT-02"
    verification:
      - kind: unit
        ref: "tests/test_card_designer.py#test_design_config_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_design_config_custom_values"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_create_gift_card_accepts_design_and_email"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_create_gift_card_design_none_backward_compat"
        status: pass
      - kind: unit
        ref: "tests/test_card_designer.py#test_design_config_accepts_sub_minimum_qr_size"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-06-30
status: complete
---

# Phase 2 Plan 02: Card Designer Summary

**Interactive Vue/Quasar card designer with drag-to-place QR + text, QR resize handle (150px min), text styling controls, custom template upload with D-03 dimension validation, and normalized fraction design config serialization**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-30T04:03:00Z
- **Completed:** 2026-06-30T04:11:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Card designer section added to create dialog with template select (portrait/landscape/custom), live drag preview, and text styling controls (font, size, color, alignment)
- Draggable QR and text elements with native pointer events and setPointerCapture — no server round-trips during drag/resize
- QR resize handle enforces minimum 150px scannable size via Math.max(minQrSize, newSize)
- Custom template upload via LNBits asset system (FormData POST /api/v1/assets?public_asset=true) with D-03 client-side dimension validation (max 1500x2000px)
- Design config serialized to normalized fractions (qr_x_frac, qr_y_frac, etc.) and sent with card creation request
- 31 new tests covering UI strings, JS methods, design config serialization, and DesignConfig model behavior — all 90 tests pass

## Task Commits

Each task was committed atomically using TDD (RED → GREEN):

1. **Task 1: Card designer UI in create dialog** — RED + GREEN
   - `3a0fde1` (test): failing tests for card designer UI and design config model
   - `0858864` (feat): card designer UI with drag, resize, styling, and template upload
2. **Task 2: Tests for card designer behavior and design config submission**
   - Tests included in `3a0fde1` (test commit) — model tests pass with existing DesignConfig from Plan 02-01, no new model code needed

## Files Created/Modified
- `static/js/index.vue` - Card Design section with template select, upload button, drag preview container, styling controls, hidden file input, and scoped CSS
- `static/js/index.js` - Design data properties, templateOptions/fontOptions/previewTextStyle computed, drag/resize methods, template upload with dimension validation, design config serialization in createGiftCard
- `tests/test_card_designer.py` - 31 tests covering Vue UI strings, JS methods and patterns, design config serialization, and DesignConfig model behavior

## Decisions Made
- Used native HTML5 pointer events with setPointerCapture instead of an external drag library — matches LNBits frontend stack (no build step, no extra deps)
- QR size stored as absolute pixels with client-side minimum of 150px (Math.max in onResize) — defense in depth with server-side clamping from Plan 02-01
- Preview dimensions: portrait 212x325px (half of 425x650), landscape 262x150px (quarter-scale of 1050x600)
- Font family mapped to CSS generic families (sans-serif/serif/monospace) for browser preview; server-side renderer uses actual DejaVu TTF files
- D-03 advisory fix: added client-side dimension validation in handleTemplateSelected — reads img.naturalWidth/naturalHeight, rejects images > 1500x2000px before upload

## Deviations from Plan

### Auto-fixed Issues

**1. [Advisory] D-03 custom-upload dimension validation not in original plan**
- **Found during:** Task 1 (template upload implementation)
- **Issue:** Plan-checker flagged that D-03 (max 1500x2000px dimension validation) was not implemented in the plan
- **Fix:** Added `_getImageDimensions` helper and dimension check in `handleTemplateSelected` — reads `img.naturalWidth`/`img.naturalHeight`, rejects oversized images with a user-facing notification before upload
- **Files modified:** static/js/index.js
- **Verification:** `test_js_has_dimension_validation` test passes (checks naturalWidth, naturalHeight, 1500, 2000 in JS content)
- **Committed in:** 0858864 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (advisory D-03 dimension validation)
**Impact on plan:** Advisory fix necessary to honor locked user decision D-03. No scope creep — validation is client-side only, ~15 lines.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. The card designer uses the existing LNBits asset system for template uploads.

## Next Phase Readiness
- Card designer is fully interactive in the create dialog with drag, resize, styling, and template upload
- Design config serialization sends normalized fractions to the create endpoint (already handled by Plan 02-01's server-side renderer)
- Plan 02-03 (magic link + email delivery) can build on this foundation — the card designer produces the design config that the email delivery flow will render
- Manual browser testing recommended: verify drag smoothness, resize handle behavior, template upload flow, and styling control responsiveness

## Self-Check: PASSED

- All 31 tests in `test_card_designer.py` pass
- All 90 tests in the full test suite pass (59 existing + 31 new)
- All acceptance criteria for both tasks verified individually
- Plan-level verification: `pytest giftcards/tests/test_card_designer.py -x` passes
- Backward compatibility: `pytest giftcards/tests/ -x` passes (all Phase 1 and Plan 02-01 tests green)
- Automated verify command: `grep` checks for card-preview, draggable-qr, resize-handle, draggable-text, Card Design, startDrag, onResize, uploadAssetFile, minQrSize, qr_x_frac, font_color — all pass

---
*Phase: 02-branded-delivery*
*Completed: 2026-06-30*
