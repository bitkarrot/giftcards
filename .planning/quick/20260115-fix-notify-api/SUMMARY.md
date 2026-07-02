---
status: complete
completed: "2026-01-15"
---

# Quick Task Summary: Fix notify API

## What changed

- `giftcards/static/js/index.js` — replaced all 19 calls to `LNbits.utils.notify(message, type)` with `Quasar.Notify.create({ message, type })`.
- `LNbits.utils.notifyApiError(error)` calls left unchanged (still exists in `window._lnbitsUtils`).

## Verification

- `node --check static/js/index.js` passes.
- Full backend test suite: **233 passed**.

## Notes

This fixes the `TypeError: LNbits.utils.notify is not a function` error reported during bulk create. After this fix, the user must still restart the LNBits server or hard-refresh the browser so the updated `index.js` is loaded (the cache key is based on `server_startup_time`).
