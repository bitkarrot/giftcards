---
slug: color-picker-right
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Move color picker swatch to the right of the label text

## Objective

In the Create Gift Card, Bulk Create, and Send Email dialogs, the color picker square currently sits to the left of the label text. Move the color swatch so it appears to the right of the label text.

## Changes

- Update the `.color-picker` CSS in `static/js/index.vue` to lay out the `q-input` control area as a flex row with the label on the left and the color input (swatch) on the right.

## Verification

- [ ] Inspect the Create Gift Card dialog: Font Color and Background Color swatches appear to the right of the label text.
- [ ] Inspect the Bulk Create dialog (same-amount mode): Font Color and Background Color swatches appear to the right of the label text.
- [ ] Inspect the Send Email dialog: Background Color swatch appears to the right of the label text.

## Files

- `giftcards/static/js/index.vue`
