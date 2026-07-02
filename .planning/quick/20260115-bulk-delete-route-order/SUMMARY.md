---
status: complete
---

# Quick Task Summary: Fix Bulk Delete 404

## What changed

- `giftcards/views_api.py` — moved the `DELETE /cards/bulk` route handler (`api_bulk_delete_cards`) above the parameterized `DELETE /cards/{card_id}` route handler (`api_delete_card`). Starlette matches routes in registration order, so the static `/bulk` segment is now resolved before the `{card_id}` parameter can swallow it.
- `giftcards/tests/test_card_management.py` — added `test_bulk_delete_route_before_parameterized_delete` regression test that verifies the route order in `giftcards_api_router`.

## Root cause

When the user selected cards and clicked **Delete Selected**, the frontend sent `DELETE /giftcards/api/v1/cards/bulk`. Because the `DELETE /{card_id}` route was registered first, Starlette treated "bulk" as a card ID and routed to `api_delete_card`. That function looked up a card with ID `"bulk"`, did not find it, and returned `404 "Gift card not found"`.

## Verification

- Full backend test suite: **236 passed** (previously 235).
- The new regression test confirms the correct route order.
- After the fix, `DELETE /cards/bulk` reaches the bulk-delete handler and returns the expected summary.

## Post-fix note

A server restart and hard browser refresh are still recommended to ensure the latest frontend code is loaded, but the backend routing fix is the only code change required.
