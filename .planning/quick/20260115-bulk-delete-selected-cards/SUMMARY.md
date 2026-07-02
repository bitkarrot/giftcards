---
status: complete
completed: "2026-01-15"
---

# Quick Task Summary: Bulk Delete Selected Cards

## What changed

- **Backend**
  - `giftcards/models.py` — added `BulkDeleteRequest` (1–500 card IDs).
  - `giftcards/crud.py` — added `get_cards_by_ids` to fetch full card records for a list of IDs.
  - `giftcards/services.py` — added `bulk_reclaim_and_delete` that deletes active/expired cards, reclaims sats for active cards, and skips redeemed cards.
  - `giftcards/views_api.py` — added `DELETE /cards/bulk` endpoint requiring admin key; validates all cards exist and belong to the wallet; returns `{status, deleted, skipped_redeemed, reclaimed_sats}`.

- **Frontend**
  - `giftcards/static/js/index.vue` — added "Delete Selected" button to the bulk action bar and a confirmation dialog showing the selected count and sats to reclaim.
  - `giftcards/static/js/index.js` — added `bulkDeleteDialog` state, `openBulkDeleteDialog`, and `confirmBulkDelete` methods that call the endpoint and refresh the table/balance.

- **Tests**
  - `giftcards/tests/test_card_management.py` — added 5 tests for bulk delete:
    - delete active cards and reclaim sats
    - skip redeemed cards
    - 403 for cross-wallet access
    - 404 for missing cards
    - empty list validation

- **Verification**
  - `.planning/phases/03-scale-manage/03-VERIFICATION.md` — updated test count, added human-verification item for bulk delete, added observable truth 03-03 #8, and updated score counts.

## Verification

- Full test suite: **233 passed**.
- UI confirmation flow captured as human-verification item.

## Post-commit fix

- Added `v-if="bulkDeleteDialog"` guard to the bulk-delete confirmation dialog and added `!this.bulkDeleteDialog` checks in `openBulkDeleteDialog` / `confirmBulkDelete` to prevent a `TypeError` when the page is loaded with a stale cached `index.js` (the template references `bulkDeleteDialog` before the new JS data is initialized). A hard browser refresh is still recommended to clear the stale cache.

## Notes

Redeemed cards are intentionally skipped (not deleted) so the operation never removes a card that has already been claimed. This matches the single-card delete behavior that returns 409 for redeemed cards.
