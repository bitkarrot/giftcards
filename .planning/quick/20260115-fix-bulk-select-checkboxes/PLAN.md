---
slug: fix-bulk-select-checkboxes
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Fix missing row selection checkboxes in gift card dashboard

## Objective

The dashboard table uses `selection="multiple"` but overrides the default Quasar header/body templates, which omits the selection checkboxes. As a result, users cannot select cards, so the "Delete Selected" and other bulk action buttons never appear.

## Root cause

`static/js/index.vue` has custom `v-slot:header` and `v-slot:body` templates for the main `q-table`. The custom header only reserves an empty column for the expand button, and the custom body only renders the expand button. Neither template includes the Quasar selection checkbox, so `v-model:selected="selectedCards"` has no UI to drive it.

## Changes

- Update the custom `header` template in `static/js/index.vue` to add a select-all checkbox column (`<q-checkbox v-model="props.selected" v-if="props.multipleSelect" dense />`).
- Update the custom `body` template to add a per-row checkbox column (`<q-checkbox v-model="props.selected" dense />`) before the expand button column.
- Keep the existing expand button column intact.

## Verification

- [ ] `node --check static/js/index.js` passes (no JS change, but sanity check).
- [ ] Backend tests pass.
- [ ] Manual browser test: open the dashboard, confirm checkboxes appear in each row and in the header, select one or more cards, and confirm the "Delete Selected (N)" button appears in the bulk action bar.

## Files

- `giftcards/static/js/index.vue`
