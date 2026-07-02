---
slug: single-create-no-design
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Add "No design (bare QR)" option to single Create Gift Card dialog

## Objective

The single-card "Create Gift Card" dialog always forces a branded design. Add a "Design Mode" selector so users can choose "No design (bare QR)" just like in the bulk create dialog.

## Changes

1. **Data model** — add `designMode: 'none'` to `createDialog.data` in `static/js/index.js`.
2. **Dialog UI** — in `static/js/index.vue`:
   - Add a `q-select` for design mode with options: `No design (bare QR)` and `Shared design`.
   - Wrap the existing template selector, preview, drag handles, and styling controls in `v-if="createDialog.data.designMode === 'shared'`.
   - Keep the design section hidden when `designMode === 'none'`.
3. **Submit handler** — in `createGiftCard`:
   - Only include `design: this.buildDesignConfig()` when `createDialog.data.designMode === 'shared'`.
   - Otherwise send `design: null` (or omit it).
4. **Reset handler** — ensure `resetCreateDialog` sets `designMode: 'none'` and resets the designer state.

## Verification

- [ ] Backend tests pass (no backend change expected).
- [ ] Manual browser test: open Create Gift Card dialog, select "No design", submit, verify card is created and redemption page/email shows bare QR.
- [ ] Manual browser test: select "Shared design", configure template, submit, verify branded card is created.

## Files

- `giftcards/static/js/index.js`
- `giftcards/static/js/index.vue`
