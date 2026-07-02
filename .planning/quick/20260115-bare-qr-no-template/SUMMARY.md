---
status: complete
completed: "2026-01-15"
---

# Quick Task Summary: Render bare QR card image without template

## Root cause

`_parse_design_config` returned `DesignConfig()` defaults when a card had no template, and `DesignConfig` defaults to `template_name="portrait"`. `_render_card_image_sync` then loaded the portrait template even for bare-QR cards.

## What changed

- `giftcards/services.py`:
  - `_parse_design_config` now returns `None` when the card has no `template_name` and no `template_asset_id`.
  - Added `_render_bare_qr_image_sync` to generate a 400x400 square white image with only a centered QR code.
  - `_render_card_image_sync` returns the bare QR image when design is `None`.
  - `render_card_image` detects `None` design and offloads the bare QR renderer to the thread pool, skipping template asset loading.

- `giftcards/tests/test_branded_image.py`:
  - Added `test_render_card_image_bare_qr_without_template` to verify the sync renderer produces a 400x400 square image, not the 425x650 portrait template.
  - Added `test_render_card_image_bare_qr_async` to verify the async renderer does the same.
- `giftcards/static/js/index.js`:
  - Added a cache-busting `?t=Date.now()` query parameter to the `Download PNG` / print URL so the browser fetches a fresh image after design changes.

## Verification

- Full test suite: **235 passed** (2 new tests).
- Manual browser test needed: create a card with "No design (bare QR)" **after** the server restart, download the PNG, and confirm it is a plain square QR code without a template.

## Important note

Cards created **before** this fix may have a design stored in the database (template_name/portrait). Those cards will still render with the portrait template. The fix only applies to new cards created with `design: null` after the backend change is deployed.
