---
slug: bulk-delete-selected-cards
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Bulk Delete Selected Cards

## Objective

Allow the issuer to delete multiple selected gift cards at once from the dashboard.

## Motivation

Users may create a bulk set of cards with the wrong design and need to redo them. A single-card delete button is too slow for this scenario.

## Assumptions / Decisions

- Bulk delete applies only to **selected cards** (via table checkboxes). A future filtered delete can be added if needed.
- **Redeemed cards are skipped**, not deleted. The operation succeeds for any active/expired cards in the selection.
- **Sats are reclaimed** for active cards, consistent with single-card delete.
- The user must confirm before deletion because it is destructive and irreversible.

## Backend changes

1. **Model** — add `BulkDeleteRequest` in `models.py`:
   - `card_ids: list[str]` (non-empty, max length maybe 500)

2. **Service** — add `bulk_reclaim_and_delete` in `services.py`:
   - Accept list of `GiftCard` objects.
   - Skip redeemed cards.
   - For active cards: reclaim sats then delete.
   - For expired cards: just delete.
   - Return summary: `deleted`, `skipped_redeemed`, `reclaimed_sats`.

3. **CRUD** — add `get_cards_by_ids` in `crud.py` (or reuse existing) to fetch selected cards for the wallet.

4. **API** — add `DELETE /cards/bulk` in `views_api.py`:
   - Requires admin key.
   - Accepts `BulkDeleteRequest` body.
   - Fetch cards, verify all belong to the wallet (any missing/forbidden returns error).
   - Call `bulk_reclaim_and_delete`.
   - Return summary.

## Frontend changes

1. **Bulk action bar** — add a "Delete Selected" button next to "Send Emails" and "Download CSV" when `selectedCards.length > 0`.
   - Use `color="negative"` and `icon="delete"`.

2. **Confirmation dialog** — add a `bulkDeleteDialog` in `index.js` and `index.vue`:
   - Show count of selected cards.
   - Warn that redeemed cards will be skipped.
   - Show estimated sats to be reclaimed (sum of active card amounts).
   - "Delete" / "Cancel" buttons.

3. **Submit handler** — `confirmBulkDelete`:
   - POST/DELETE to new endpoint.
   - Show result notification with counts.
   - Clear `selectedCards` and reload table.

## Verification

- [ ] Automated backend tests for bulk delete endpoint:
  - deletes selected active cards and reclaims sats
  - skips redeemed cards
  - returns 403 if a card belongs to another wallet
  - returns 400 for empty list
- [ ] Human UAT: select multiple cards, click Delete Selected, confirm, verify cards removed and notification shows summary.

## Files

- `giftcards/models.py`
- `giftcards/services.py`
- `giftcards/crud.py`
- `giftcards/views_api.py`
- `giftcards/static/js/index.js`
- `giftcards/static/js/index.vue`
- `giftcards/tests/test_card_management.py`
