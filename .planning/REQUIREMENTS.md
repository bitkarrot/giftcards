# Requirements: LNBits Gift Cards Extension

**Defined:** 2026-06-29
**Core Value:** Anyone can create and redeem a sats-denominated gift card with a unique, secure redemption link.

## v1 Requirements

### Gift Card Creation (GCARD)

- [x] **GCARD-01**: Issuer can create a single gift card with a fixed sats amount.
- [x] **GCARD-02**: Issuer can set an expiration date on a gift card at creation time.
- [x] **GCARD-03**: Issuer can add recipient name, sender name, and a personal message to a gift card.
- [x] **GCARD-04**: Each gift card receives a unique, unguessable redemption token and a shareable redemption link.
- [x] **GCARD-05**: Issuer wallet is debited the gift card amount when the card is created (locked funding).

### Redemption (REDM)

- [x] **REDM-01**: Recipient can open the unique redemption link and view the gift card value and sender message.
- [x] **REDM-02**: Recipient can redeem the gift card by scanning the QR code with a Lightning wallet.
- [x] **REDM-03**: Each gift card can only be redeemed once; concurrent redemption attempts do not double-spend.
- [x] **REDM-04**: Expired gift cards cannot be redeemed and display an expired status to the recipient.
- [x] **REDM-05**: Sats from unclaimed, expired gift cards are automatically returned to the issuer wallet.

### Delivery (DELV)

- [ ] **DELV-01**: Gift card can be delivered to a recipient by email as a PNG image attachment.
- [ ] **DELV-02**: Email delivery includes the sender's personal message and a link to redeem the gift card.
- [ ] **DELV-03**: Gift card can be delivered to a nostr npub as a direct message containing the redemption link.
- [ ] **DELV-04**: Issuer can download a printable gift card image (PNG) for manual distribution.

### Templates (TPLT)

- [ ] **TPLT-01**: Gift card image can use a sample template (e.g., Christmas, birthday, generic gift card).
- [ ] **TPLT-02**: Issuer can choose the QR code placement on the gift card image (e.g., corner, center).
- [ ] **TPLT-03**: Gift card image renders the sats amount, recipient name, and sender message on the chosen template.

### Bulk Creation (BULK)

- [ ] **BULK-01**: Issuer can create multiple gift cards with the same sats amount from a single form.
- [ ] **BULK-02**: Issuer can upload a CSV file with columns for recipient name, sats amount, email address, and nostr npub to create gift cards in bulk.
- [ ] **BULK-03**: Bulk CSV creation validates each row and reports per-row errors before creating any cards.
- [ ] **BULK-04**: Bulk creation generates a unique redemption link and optional email/nostr delivery for each card.

### API (API)

- [ ] **API-01**: External systems can create gift cards via an authenticated REST API endpoint.
- [ ] **API-02**: External systems can retrieve gift card status and details via an authenticated REST API endpoint.
- [ ] **API-03**: All issuer-facing API endpoints require an LNBits admin or invoice key and are scoped to the authenticated wallet.

### Dashboard (DASH)

- [ ] **DASH-01**: Issuer can view a list of all gift cards they have created.
- [ ] **DASH-02**: Issuer can filter gift cards by status (created, active, redeemed, expired, cancelled).
- [ ] **DASH-03**: Issuer can view gift card details including status, creation date, expiration date, and redemption date.

## v2 Requirements

### Audit & Refund (AUDT)

- **AUDT-01**: Issuer can view a per-card audit log of create, email, view, redeem, expire, and cancel events.
- **AUDT-02**: Issuer can cancel an active gift card and automatically reclaim its sats.

### Print & Delivery (PRNT)

- **PRNT-01**: Issuer can download a printable PDF of a gift card or a batch cut sheet.
- **PRNT-02**: SMS delivery option via a pluggable provider.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Partial spend / balance-preserving redemption | Requires custodial sub-accounting and partial LNURL-withdraw logic; no Lightning-native standard supports it. |
| Fiat-denominated gift cards | Exchange rate volatility and regulatory exposure conflict with the sats-native LNBits model. |
| Physical card printing fulfillment | Out of scope; only digital image/PDF generation is provided. |
| Real-time WebSocket status push for dashboard | Polling is sufficient for the admin dashboard; websockets add infrastructure complexity with no recipient benefit. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GCARD-01 | Phase 1 | Complete |
| GCARD-02 | Phase 1 | Complete |
| GCARD-03 | Phase 1 | Complete |
| GCARD-04 | Phase 1 | Complete |
| GCARD-05 | Phase 1 | Complete |
| REDM-01 | Phase 1 | Complete |
| REDM-02 | Phase 1 | Complete |
| REDM-03 | Phase 1 | Complete |
| REDM-04 | Phase 1 | Complete |
| REDM-05 | Phase 1 | Complete |
| DELV-01 | Phase 2 | Pending |
| DELV-02 | Phase 2 | Pending |
| DELV-03 | Phase 2 | Pending |
| DELV-04 | Phase 2 | Pending |
| TPLT-01 | Phase 2 | Pending |
| TPLT-02 | Phase 2 | Pending |
| TPLT-03 | Phase 2 | Pending |
| BULK-01 | Phase 3 | Pending |
| BULK-02 | Phase 3 | Pending |
| BULK-03 | Phase 3 | Pending |
| BULK-04 | Phase 3 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |
| DASH-01 | Phase 3 | Pending |
| DASH-02 | Phase 3 | Pending |
| DASH-03 | Phase 3 | Pending |

**Coverage:**

- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-29*
*Last updated: 2026-06-29 after Phase 1 verification — all 10 Phase 1 requirements marked Complete (Phase 2: 7 reqs, Phase 3: 10 reqs)*
*Post-session update: 2026-06-29 — Architecture changed to no per-card wallets (withdraw extension pattern). raw_token now stored in DB (migration m002) for redemption_url reconstruction. GCARD-05 still satisfied: issuer wallet debited at creation time.*
