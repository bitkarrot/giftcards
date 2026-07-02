---
slug: bare-qr-no-template
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Render bare QR card image without template when design is absent

## Objective

When a gift card is created with "No design (bare QR)", the card image endpoint still renders the portrait template behind the QR code. The image should be a plain QR code without any template.

## Root cause

`_parse_design_config` returns `DesignConfig()` defaults when `template_name` and `template_asset_id` are `None`. The default `DesignConfig` has `template_name = "portrait"`, so `_render_card_image_sync` loads the portrait template.

## Changes

1. `giftcards/services.py`:
   - Make `_parse_design_config` return `None` when the card has no design (both `template_name` and `template_asset_id` are `None`).
   - Update `_render_card_image_sync` to generate a bare QR image when design is `None`.
   - Update `render_card_image` to skip template asset loading when design is `None`.
2. `giftcards/views_api.py`:
   - Optionally, `api_get_public_card` already returns `has_design=False` correctly; no change needed.

## Bare QR image spec

- Square image (e.g., 400x400 base, scaled by `scale`).
- White background.
- QR code centered in the image.
- No text or template overlay.

## Verification

- [ ] Existing tests still pass.
- [ ] New test: create a card with `design=None`, call `_render_card_image_sync`, and verify the output is a square image without a template.
- [ ] Manual browser test: create a card with "No design (bare QR)", download the PNG, and confirm it is a plain QR code.

## Files

- `giftcards/services.py`
- `giftcards/views_api.py` (if needed)
- `giftcards/tests/test_branded_image.py` or similar
