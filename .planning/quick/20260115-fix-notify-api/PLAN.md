---
slug: fix-notify-api
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Replace LNbits.utils.notify with Quasar.Notify.create

## Objective

Fix the `TypeError: LNbits.utils.notify is not a function` error that occurs during frontend actions (e.g., bulk create).

## Background

`window._lnbitsUtils` (exposed as `LNbits.utils`) does not have a `notify` method. The existing extension code was calling `LNbits.utils.notify(message, type)`, which throws because the function is undefined. The correct Quasar API is `Quasar.Notify.create({ message, type })`.

## Changes

- Replace all 19 occurrences of `LNbits.utils.notify(message, type)` in `static/js/index.js` with `Quasar.Notify.create({ message, type })`.
- Leave `LNbits.utils.notifyApiError(error)` unchanged (that function still exists).

## Verification

- `node --check static/js/index.js` passes.
- Backend test suite passes (frontend-only change, no functional backend impact).
- Manual browser test: perform an action that triggers a notification (e.g., bulk create) and confirm the notification appears instead of a console error.

## Files

- `giftcards/static/js/index.js`
