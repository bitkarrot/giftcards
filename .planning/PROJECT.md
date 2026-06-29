# LNBits Gift Cards Extension

## What This Is

An LNBits extension that lets wallet holders create, customize, distribute, and redeem Bitcoin Lightning gift cards denominated in sats. Gift cards can be designed individually or in bulk, delivered as unique redemption links or printable/scannable QR images, and expired automatically if not claimed.

## Core Value

Anyone can create and redeem a sats-denominated gift card with a unique, secure redemption link.

## Business Context

- **Customer**: LNBits users (wallet holders) who want to gift sats to friends, customers, or event attendees.
- **Revenue model**: None directly; drives LNBits wallet usage and Lightning payment volume.
- **Success metric**: A recipient can create, redeem, and spend a gift card end-to-end without manual admin intervention.
- **Strategy notes**: LNBits extension architecture; should follow existing extension patterns (e.g., events extension exists as reference but structural differences expected).

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Create single gift cards with a fixed sats amount and optional recipient metadata.
- [ ] Create gift cards in bulk by uploading a CSV with recipient name, sats amount, and email or nostr npub.
- [ ] Redeem gift cards via a unique, shareable redemption link or by scanning a QR code.
- [ ] Set and enforce expiration dates on gift cards; expired cards become unredeemable.
- [ ] Customize gift card design by choosing QR code placement or selecting from sample templates (e.g., Christmas, birthday, generic gift card).
- [ ] Deliver gift cards to recipients by email as an image attachment with a message from the sender.
- [ ] Provide API endpoints for dynamic creation of gift cards.
- [ ] Admin/issuer dashboard to view, manage, and track gift card status.

### Out of Scope

- **Integration with external fiat on-ramps** — This extension operates purely on sats within LNBits; fiat conversion is handled elsewhere.
- **Multi-currency support** — v1 is sats-only; other currencies can be added later if needed.
- **Physical card printing fulfillment** — Printable cards are generated as images/PDFs; we do not print or mail physical cards.
- **Advanced analytics/CRM** — Basic status tracking only; no recipient marketing automation.
- **Lightning Address or NIP-57 zaps for redemption** — Redemption is via unique link/QR; zaps may be added later.

## Context

- LNBits is a free and open-source Lightning wallet/account system with an extension model.
- An events extension exists in the workspace as a structural reference but is not a direct copy target.
- Gift cards must be secure-by-default: each card gets a unique redemption token and should not be guessable.
- The extension should support both manual design and batch workflows for events, holidays, and marketing use cases.
- Recipients may not have LNBits accounts; redemption should work for guests.

## Constraints

- **Tech stack**: Must be built as an LNBits extension, matching the runtime version and conventions of the target LNBits installation.
- **Security**: Redemption links/tokens must be unguessable and single-use (or idempotent for the intended recipient).
- **Compatibility**: Must work alongside existing LNBits wallet and account system without breaking core flows.
- **Performance**: Bulk creation of hundreds of cards should be responsive; image generation should not block the request thread.
- **Privacy**: Recipient email/nostr npub is stored only as needed for delivery and should not be exposed publicly.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build as an LNBits extension (not standalone) | Reuses LNBits wallet, auth, and Lightning infrastructure | — Pending |
| Use unique redemption links + QR codes | Works for both digital delivery and printouts | — Pending |
| Support CSV bulk upload + API | Covers event/holiday use cases and automation | — Pending |
| Sats-denominated only | Aligns with LNBits native unit; defers currency complexity | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-29 after initialization*
