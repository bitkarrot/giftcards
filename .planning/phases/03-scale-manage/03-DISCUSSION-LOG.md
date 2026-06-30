# Phase 3: Scale & Manage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 3-Scale & Manage
**Areas discussed:** Bulk form UX, CSV upload format, REST API design, Dashboard filters

---

## Bulk form UX

### Q1: How does the issuer specify the number of cards?

| Option | Description | Selected |
|--------|-------------|----------|
| Number input | Simple numeric field: "How many cards?" — issuer types a number | ✓ |
| Slider + input | Slider with a number input beside it | |
| Dynamic recipient list | Issuer adds rows dynamically with optional recipient name + email | |

**User's choice:** Number input
**Notes:** Cleanest UI, fastest for known quantities.

### Q2: Where in the UI should bulk creation live?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate button + dialog | "Bulk Create" button next to "Create Gift Card", opens separate dialog | ✓ |
| Tab inside create dialog | Toggle/tab inside existing create dialog: Single / Bulk / CSV | |
| Dropdown menu | Replace single button with dropdown: Create Single / Create Bulk / Create CSV | |

**User's choice:** Separate button + dialog
**Notes:** Two entry points, two dialogs. Keeps single-create and bulk as distinct flows.

### Q3: After bulk creation completes, what does the issuer see?

| Option | Description | Selected |
|--------|-------------|----------|
| Results table + CSV export | Table of created cards with Download CSV button | |
| Toast + dashboard refresh | Success toast, refresh card list | |
| Results + auto-deliver | Results table with Send all emails button | |

**User's choice:** Other (free text)
**Notes:** "Toast + dashboard refresh, there should be a button for CSV export or Send all emails. The dashboard should also enable editing of individual entries and for deletion of entries." — This expanded the scope to include card editing, deletion, and bulk dashboard actions.

### Q4: What fields can the issuer edit on an existing card?

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata only | recipient name, sender name, message, email. No amount. | |
| All fields incl. amount | Edit all metadata including amount | ✓ |
| Email + delivery only | Only recipient email and re-trigger delivery | |

**User's choice:** All fields incl. amount
**Notes:** Led to follow-up about how amount editing works given cards are funded at creation.

### Q5: How should amount editing work?

| Option | Description | Selected |
|--------|-------------|----------|
| Charge/refund difference | Charge wallet for increases, refund for decreases | |
| Cancel + recreate | Cannot change amount; cancel card and create new one | ✓ |
| Only pre-funding | Allow amount change only for unfunded cards | |

**User's choice:** Cancel + recreate
**Notes:** Amount field in edit dialog shows a notice: "To change the amount, cancel this card and create a new one." All other fields are directly editable.

### Q6: What are the rules for deleting a card?

| Option | Description | Selected |
|--------|-------------|----------|
| Non-redeemed only | Only created/active/expired cards. Reclaim sats first. | ✓ |
| Any status | Delete any card regardless of status | |
| Cancel (soft delete) | Mark as cancelled, keep record for audit | |

**User's choice:** Non-redeemed only
**Notes:** Hard delete, not soft delete. Reclaims sats for active cards. Expired cards already reclaimed by expiry task. AUDT-02 soft delete is v2.

---

## CSV upload format

### Q1: Which CSV columns are required vs optional?

| Option | Description | Selected |
|--------|-------------|----------|
| Name + amount required | recipient_name, amount_sats required; email, npub, sender, message optional | ✓ |
| Amount only required | Only amount_sats required; everything else optional | |
| Name + amount + email required | All delivery-target fields required | |

**User's choice:** Name + amount required
**Notes:** Email/npub optional since not all cards need delivery. Matches BULK-02 spec.

### Q2: Does the CSV support card design config?

| Option | Description | Selected |
|--------|-------------|----------|
| No design in CSV | Amount + recipient only, design applied afterward | |
| One design for all rows | Pick design once in dialog, applies to all rows | |
| Per-row design columns | CSV includes per-row design columns | |

**User's choice:** Other (free text)
**Notes:** "allow per-row design columns and option for no design or one design for all rows" — Three-way choice: No design / One design for all / Per-row design columns. Selector appears in the CSV tab of the bulk dialog.

### Q3: How are CSV validation errors shown?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-row validation table | Green/red per row, fix all before proceeding | |
| Summary + partial create | X valid, Y errors, option to create valid only | |
| Both (table + summary) | Per-row table AND summary, must fix all errors | ✓ |

**User's choice:** Both (table + summary)
**Notes:** Strictest validation. No partial create. Matches BULK-03 exactly.

### Q4: What's the maximum CSV row count?

| Option | Description | Selected |
|--------|-------------|----------|
| 500 rows max | Sufficient for events and holidays | ✓ |
| 1000 rows max | Larger events, may need background processing | |
| No hard limit | Process in batches with progress bar | |

**User's choice:** 500 rows max
**Notes:** Keeps requests responsive. Planner validates row count on upload.

---

## REST API design

### Q1: Should the API mirror existing endpoints or have a separate bulk endpoint?

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror existing + bulk endpoint | Same endpoints + POST /cards/bulk | ✓ |
| Separate bulk endpoint only | Separate /bulk endpoint, single stays on existing | |
| Unified single + array | One endpoint accepts single or array | |

**User's choice:** Mirror existing + bulk endpoint
**Notes:** Minimal new code, consistent with existing patterns.

### Q2: Which operations get invoice-key access?

| Option | Description | Selected |
|--------|-------------|----------|
| Admin=write, Invoice=read | Admin for creates/deletes, invoice for list/detail | ✓ |
| Admin key only | All operations require admin key | |
| Admin=write, Invoice=status-only | Invoice key for lightweight status check only | |

**User's choice:** Admin=write, Invoice=read
**Notes:** Fulfills D-11 deferred from Phase 1. Satisfies API-03.

### Q3: What does the card status/detail API response include?

| Option | Description | Selected |
|--------|-------------|----------|
| Full detail, no token | All metadata, no redemption URL | |
| Full detail + redemption URL | Everything including redemption link | |
| Optional link flag | Default no URL, ?include_link=true adds it | ✓ |

**User's choice:** Optional link flag
**Notes:** Balances security (raw_token not exposed by default) with integration needs. External systems opt in.

---

## Dashboard filters

### Q1: Which filters does the dashboard need?

| Option | Description | Selected |
|--------|-------------|----------|
| Status + text search | Status dropdown + free-text search | |
| Status + search + date range | Status + search + date range picker | ✓ |
| All filters | Status + search + date + delivery status + amount range | |

**User's choice:** Status + search + date range
**Notes:** Covers DASH-02 for common filter use cases without over-complicating the UI.

### Q2: How should the card detail view work?

| Option | Description | Selected |
|--------|-------------|----------|
| Expand row (current) | Expand row in q-table, all details inline | |
| Separate detail page | Navigate to /giftcards/manage/{card_id} | |
| Expand row + detail dialog | Expand for quick view, dialog for full details | ✓ |

**User's choice:** Expand row + detail dialog
**Notes:** Hybrid approach. Expand row for quick summary + key actions, "View full details" button opens dialog with everything including branded image preview.

### Q3: Should bulk actions be global or per-selection?

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-select + bulk actions | Checkboxes on rows, bulk action bar | |
| Global bulk buttons only | Global buttons above table, apply to all filtered | |
| Both global + multi-select | Global buttons for filtered + checkboxes for targeted | ✓ |

**User's choice:** Both global + multi-select
**Notes:** Global buttons ("Send all (filtered)", "Download CSV (filtered)") + multi-select checkboxes for targeted actions on specific cards.

---

## Claude's Discretion

- CSV column naming convention (snake_case vs camelCase) — must be documented with downloadable template
- Exact design column names in per-row CSV mode — must map to existing DesignConfig fields
- CSV parsing library (Python stdlib `csv` module sufficient)
- Bulk creation transaction strategy (all-or-nothing vs batch-with-progress)
- API response format for bulk creation (array vs summary)
- Date range picker UI component (Quasar QDate or similar)
- Multi-select checkbox implementation in Quasar q-table
- Detail dialog layout and component structure
- Edit dialog form structure and validation
- Whether bulk "Send all emails" runs synchronously or as background task

## Deferred Ideas

- Nostr delivery (DELV-03) — still deferred from Phase 2
- Audit log per card (AUDT-01) — v2
- Cancel/soft-delete with audit trail (AUDT-02) — v2
- Printable PDF / cut sheet (PRNT-01) — v2
- SMS delivery (PRNT-02) — v2
- Background job for bulk email sending — planner's discretion for Phase 3
- Webhook notifications for card status changes — future enhancement
- Rate limiting on API endpoints — deferred (follows Phase 1 D-06 pattern)
