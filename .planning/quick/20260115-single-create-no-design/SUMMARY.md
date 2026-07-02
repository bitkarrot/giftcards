---
status: complete
completed: "2026-01-15"
---

# Quick Task Summary: Add "No design (bare QR)" to single create dialog

## What changed

- `giftcards/static/js/index.js`:
  - Added `designMode: 'none'` to `createDialog.data` and `resetCreateDialog`.
  - Updated `createGiftCard` to send `design: null` when `designMode === 'none'`, and `design: buildDesignConfig()` when `designMode === 'shared'`. The `designMode` field is stripped from the API payload.

- `giftcards/static/js/index.vue`:
  - Added a "Design Mode" `q-select` to the single Create Gift Card dialog with options `No design (bare QR)` and `Shared design`.
  - Wrapped the template selector, preview, drag handles, and styling controls in `v-if="createDialog.data.designMode === 'shared'"` so they are hidden in bare-QR mode.

## Verification

- `node --check static/js/index.js` passes.
- Full backend test suite: **233 passed**.
- Manual browser test needed: open Create Gift Card dialog, select "No design (bare QR)", submit, and verify the card is created without a branded design.
