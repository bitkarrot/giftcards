---
status: in-progress
---

# Quick Task Plan: Fix Bulk Delete 404

## Objective

Fix the 404 "Gift card not found" error that occurs when selecting cards in the dashboard and clicking **Delete Selected**.

## Root cause

The `DELETE /cards/bulk` endpoint was registered in `views_api.py` **after** the parameterized `DELETE /cards/{card_id}` endpoint. Starlette matches routes in registration order, so a request to `DELETE /cards/bulk` was captured by the `/{card_id}` route with `card_id="bulk"`. The backend then tried to look up a card whose ID is the string `"bulk"`, failed, and returned 404.

## Fix

Move `api_bulk_delete_cards` (the `DELETE /cards/bulk` route) **before** `api_delete_card` (the `DELETE /cards/{card_id}` route) in `views_api.py` so the static `/bulk` path is matched first.

## Verification

- Add a regression test in `tests/test_card_management.py` that asserts the `DELETE /cards/bulk` route is registered before the `DELETE /cards/{card_id}` route.
- Run the full test suite: `python -m pytest tests/`
- Expected: all tests pass.

## Files

- `giftcards/views_api.py`
- `giftcards/tests/test_card_management.py`
