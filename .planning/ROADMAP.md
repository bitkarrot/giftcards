# Roadmap: LNBits Gift Cards Extension

## Overview

Build a complete Bitcoin Lightning gift card system as a LNBits extension. The journey moves from the core atomic loop (create + redeem a sats-denominated card securely) to branded visual delivery (templates, email, nostr, printable download) and finally to scale and management (bulk CSV creation, REST API, and the issuer dashboard). Each phase ships a vertical slice that is usable end-to-end before the next phase begins.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Core Loop** - Issuer can create a funded gift card and a recipient can redeem it end-to-end
- [ ] **Phase 2: Branded Delivery** - Issuer can design a branded card image and deliver it via email, nostr, or printable download
- [ ] **Phase 3: Scale & Manage** - Issuer can bulk-create cards, automate via REST API, and manage card status from a dashboard

## Phase Details

### Phase 1: Core Loop

**Mode:** mvp
**Goal**: Anyone can create a sats-denominated gift card with a unique secure redemption link and a recipient can redeem it via Lightning — the full end-to-end loop — before any other feature is built.
**Depends on**: Nothing (first phase)
**Requirements**: GCARD-01, GCARD-02, GCARD-03, GCARD-04, GCARD-05, REDM-01, REDM-02, REDM-03, REDM-04, REDM-05
**Success Criteria** (what must be TRUE):

  1. Issuer can create a gift card specifying a sats amount, expiration date, recipient name, sender name, and personal message; the issuer wallet is debited at creation time.
  2. Each created card has a unique, unguessable redemption link that can be shared; opening that link shows the card value and sender message.
  3. Recipient can redeem the card by scanning the QR code with any Lightning wallet; the payout completes successfully.
  4. A card that has already been redeemed cannot be redeemed again, and concurrent redemption attempts do not result in double-spend.
  5. An expired card displays an expired status and cannot be redeemed; any locked sats are automatically returned to the issuer wallet.

**Plans**: 2/3 plans executed

Plans:

- [x] 01-01-PLAN.md — Walking skeleton: create, fund, and redeem a gift card end-to-end ✅ 2026-06-29
- [x] 01-02-PLAN.md — Harden redemption: atomic guard, concurrency, and failure recovery ✅ 2026-06-29
- [ ] 01-03-PLAN.md — Expiry sweep, sats reclaim, and security acceptance review

**UI hint**: yes

### Phase 2: Branded Delivery

**Mode:** mvp
**Goal**: Issuer can attach a branded image design to a gift card and deliver it to the recipient via email (with image attachment), nostr DM, or printable PNG download — turning the bare redemption link into a recognizable gift card experience.
**Depends on**: Phase 1
**Requirements**: TPLT-01, TPLT-02, TPLT-03, DELV-01, DELV-02, DELV-03, DELV-04
**Success Criteria** (what must be TRUE):

  1. Issuer can choose a design template (e.g., Christmas, birthday, generic) and configure QR code placement; the rendered card image shows the sats amount, recipient name, and sender message.
  2. Issuer can trigger email delivery; the recipient receives an email with the branded card as a PNG attachment, the sender's message, and a working redemption link.
  3. Issuer can trigger nostr delivery; the recipient's nostr npub receives a DM containing the redemption link.
  4. Issuer can download a printable PNG image of the gift card for manual distribution.

**Plans**: TBD
**UI hint**: yes

### Phase 3: Scale & Manage

**Mode:** mvp
**Goal**: Issuer can create gift cards in bulk (same-amount form or variable-amount CSV), automate card creation and lookup via a REST API, and manage all issued cards through a filterable dashboard.
**Depends on**: Phase 2
**Requirements**: BULK-01, BULK-02, BULK-03, BULK-04, API-01, API-02, API-03, DASH-01, DASH-02, DASH-03
**Success Criteria** (what must be TRUE):

  1. Issuer can create N gift cards at once from a single form (same amount); each card gets a unique redemption link with optional delivery.
  2. Issuer can upload a CSV with per-recipient name, sats amount, email, and nostr npub; the system validates each row before creating any cards and reports per-row errors.
  3. External systems can create gift cards and retrieve card status via authenticated REST API endpoints scoped to the issuer's LNBits wallet key.
  4. Issuer can view a list of all created cards, filter by status (created, active, redeemed, expired, cancelled), and inspect individual card details including creation, expiration, and redemption dates.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Loop | 2/3 | In Progress|  |
| 2. Branded Delivery | 0/TBD | Not started | - |
| 3. Scale & Manage | 0/TBD | Not started | - |
