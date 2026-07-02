---
status: complete
completed: "2026-01-15"
---

# Quick Task Summary: Fix missing row selection checkboxes

## Root cause

The dashboard `q-table` uses `selection="multiple"` with `v-model:selected="selectedCards"`, but the custom `header` and `body` slots did not render the Quasar selection checkboxes. This made it impossible to select cards, so the bulk action bar (including "Delete Selected") never appeared.

## What changed

- `giftcards/static/js/index.vue`:
  - Added a select-all checkbox in the custom `header` template (`<q-checkbox v-model="props.selected" v-if="props.multipleSelect" dense />`).
  - Added a per-row checkbox in the custom `body` template (`<q-checkbox v-model="props.selected" dense />`) before the expand button column.
  - Kept the existing expand button and column layout intact.

## Verification

- `node --check static/js/index.js` passes.
- Full backend test suite: **235 passed**.
- Manual browser test needed: confirm checkboxes appear in the dashboard header and rows, select one or more cards, and verify the bulk action bar with "Delete Selected (N)" appears.
