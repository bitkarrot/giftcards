---
slug: icon-only-toolbar-expanded-row
created: "2026-01-15"
source: user
type: quick
---

# Quick Task: Icon-Only Toolbar for Expanded Dashboard Row

## Objective

Apply Proposal 2 (icon-only action toolbar) to the gift card dashboard expanded row in `static/js/index.vue`.

## Motivation

The current expanded row uses dense text-labeled buttons for all five actions (Send Email, Download PNG, View Full Details, Edit, Delete). This creates visual clutter and mixes destructive actions with primary actions. The user selected Proposal 2 from the mockup for a cleaner, more compact layout.

## Changes

1. **Metadata section**
   - Keep the existing two-column grid for From / Message.
   - Add Created / Status inline row to give the expanded row more informational density.
   - Use the meta-label style (small, muted text) for consistency.

2. **Redemption link section**
   - Keep the link in a read-only `q-input`.
   - Use only a flat icon copy button in the append slot (no text label).

3. **Action toolbar**
   - Convert the five action buttons to **round, flat, icon-only** buttons.
   - Add `q-tooltip` to each button for discoverability.
   - Group the four non-destructive actions together (Send Email, Download PNG, View Details, Edit).
   - Visually separate the **Delete** button with a `q-separator` (vertical) and place it on the right side.
   - Use `row items-center justify-between` so the delete action stays aligned to the right and the group wraps naturally on small screens.

## Icons

| Action | Icon | Color |
|--------|------|-------|
| Send Email | mail | primary |
| Download PNG | download | primary |
| View Full Details | info | grey |
| Edit | edit | grey |
| Delete | delete | negative |

## Verification

- [ ] Visual check of the mockup match in both light and dark mode.
- [ ] All existing `aria-label` attributes preserved.
- [ ] Existing `q-tooltip` disable messages for redeemed cards preserved.
- [ ] No functional changes to click handlers or dialog behavior.
- [ ] `ruff` / `prettier` formatting not required for this Vue-only change (no Python changes).

## Files

- `static/js/index.vue` (expanded row template, ~lines 173–275)
