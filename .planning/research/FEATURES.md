# Feature Research

**Domain:** LNBits extension — Lightning gift cards / sats vouchers
**Researched:** 2026-06-29
**Confidence:** MEDIUM (cross-checked across 8+ products; Lightning-specific nuances LOW, general gift card standards MEDIUM-HIGH)

---

## Competitive Landscape Summary

Products surveyed: **Azteco**, **Lightning TipCards** (Satoshi Engineering), **LN Gift** (Lnfi Network), **ZBD Vouchers**, **btc-giftcard** (open source Go), **coin-gift**, **UniVoucher**, **BitGifty**, **Codego**, and industry benchmarks from **BHN/NAPCO 2025 Digital Gift Card Programs Report** (100 programs).

**Key gap:** No existing Lightning-native product combines all of: email delivery with branded image, CSV bulk import with per-recipient variable amounts, design templates, expiry date enforcement, and issuer dashboard. This extension fills that gap inside the LNBits ecosystem.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Unique, unguessable redemption link / QR code | Every gift card product from Azteco to enterprise platforms generates a unique per-card token; users won't trust a guessable code | LOW | 16+ chars of entropy; use `secrets.token_urlsafe` or UUID v4. Wrap in LNURL-withdraw. |
| Single-use enforcement | Prevents double-spend; universally expected from any digital voucher | MEDIUM | LNURL-w protocol handles pull idempotency; must also mark card `redeemed` in DB atomically with LNBits wallet debit. |
| Fixed sats amount per card | Recipient needs to know what they'll receive; variable amounts confuse non-crypto users | LOW | Store as `sats_amount` on card record; fund LNBits sub-wallet at creation. |
| Issuer dashboard — view all cards and status | Standard in every gift card admin tool (Recurly, Giftbit, eGifter, voucherify); issuers need to track what's out there | MEDIUM | Status states: `created → active → redeemed / expired`. Searchable/filterable list. |
| Card status lifecycle | Issued, active, redeemed, expired, cancelled — all standard (BHN/NAPCO benchmark criteria) | LOW | DB enum; UI filter tabs. |
| Expiration date enforcement | Industry standard; unclaimed funds must have a policy; LNBits has no built-in LNURLw expiry | MEDIUM | Cron/background task checks expiry; expired cards return "invalid" at redemption time; issuer can reclaim sats from sub-wallet. |
| Recipient-friendly redemption page | Recipient opens link in browser, sees card value, scans/taps to claim with any Lightning wallet | MEDIUM | Mobile-first HTML. On scan with camera (non-wallet), LNBits creates instant wallet — use this path. |
| QR code as scannable image | Every Lightning gift product produces QR codes; print + digital use requires high-quality image | LOW | Python `qrcode` lib or JS `qrcode` library; embed in card image. |
| Personalization — sender name + message | BHN benchmark: universally present in top programs; makes it feel like a gift vs. a voucher | LOW | `sender_name`, `message` fields on card; shown on redemption page. |
| Email delivery with card attached | BHN benchmark: top 9/10 programs offer email; average delivery time 22 min; now baseline expectation | HIGH | SMTP via LNBits settings or configurable SMTP; card rendered as image/PNG attachment. Async task (do not block creation). |
| API endpoints for programmatic creation | Required for automation use cases; all serious platforms (ZBD, BitGifty, Azteco B2B) expose this | MEDIUM | REST: `POST /api/v1/giftcards`, `GET /api/v1/giftcards/{id}`. LNBits extension API pattern. |
| Reclaim / recover unclaimed sats | Issuers expect to get funds back from expired or cancelled cards; failing to do so is a hidden liability | MEDIUM | On expiry, transfer sats from card sub-wallet back to issuer wallet. Manual cancel also triggers reclaim. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| CSV bulk upload with per-recipient variable amounts | No Lightning-native product does this; enterprise platforms (Giftbit) do. Unlocks events, HR rewards, holiday campaigns with different amounts per person | HIGH | CSV columns: `recipient_name`, `sats_amount`, `email` (optional), `nostr_npub` (optional). Server-side validation with preview before commit. Creates N cards + N sub-wallets in one request. |
| Design templates (Christmas, birthday, generic) | TipCards and LNBits withdraw have custom SVG support but no gallery; a curated template library turns a technical tool into a consumer product | MEDIUM | 3–5 SVG/PNG templates at launch; QR code position configurable (corner/center). Stored as extension static assets. |
| Nostr npub delivery | Beyond email; reaches Bitcoin-native audience on their preferred channel; no Lightning gift card currently does this natively in LNBits | HIGH | Requires NIP-04 or NIP-17 DM. Optional alongside email — adds npub field to card; send redemption link as DM. Dependency: nostr key for extension or user-provided nsec. |
| Branded/printable card image (PDF/PNG download) | Physical-style gifting; TipCards supports print but no design templates; this extension adds templates + PDF output | MEDIUM | Server-side image composition (Pillow/canvas); QR + template + amount + message. Download from issuer dashboard. |
| Bulk creation from single form (same amount) | LNBits Quick Vouchers already does this but without the gift card UX; this extension elevates it with theming, email, and tracking | LOW | N cards, same amount, same template. UI slider for count. Complement to CSV path. |
| Walletless guest redemption path | LNBits LNURL-w already creates instant LNBits wallet on QR scan — expose this explicitly in the redemption UI | LOW | "Don't have a wallet? Scan with camera → get instant wallet." Onboards non-Lightning users. |
| Cancel + refund flow | Some products (LN Gift: 24h refund on expiry) handle this; issuers need assurance | MEDIUM | Cancel card → return sats to issuer wallet → mark `cancelled`. Should be audit-logged. |
| Per-card audit log | Enterprise platforms (eGifter, Giftbit) show every event; Lightning TipCards shows funded/viewed/redeemed per card | MEDIUM | Events: created, emailed, viewed, redemption attempted, redeemed, expired, cancelled. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Partial spend / balance-preserving redemption | btc-giftcard implements this; feels natural for large denominations | Requires custodial balance accounting, partial LNURL-w logic, and a "remaining balance" UI — enormous complexity for v1; no standard Lightning protocol supports it natively | Single-use, full-amount redemption only. Issuers should size cards appropriately. |
| Fiat denomination display (USD/EUR) | Recipients understand dollar amounts better than sats | Exchange rate fetching, conversion at redemption time, rate-lock debates, regulatory exposure — all scope explosion for a sats-native LNBits tool | Show sats prominently; optionally show approximate fiat in small text at creation time only (read from LNBits rate endpoint, not stored). |
| SMS delivery | BHN benchmark: 9/10 top programs offer SMS; fastest delivery | Requires Twilio/Vonage integration, phone number storage, international SMS cost variability, carrier regulations — out of scope for a self-hosted extension | Email is the v1 delivery channel. SMS can be added in v2 via pluggable delivery provider interface. |
| Lightning Address redemption (LN Address or NIP-57 zaps) | Power users want to receive to LN Address | Requires reverse-direction payment push (issuer pays out), not a pull; fundamentally different flow from LNURL-w; adds wallet-side complexity | LNURL-w pull model. Recipient provides their wallet; wallet pulls sats. |
| Multi-currency / ERC-20 tokens | UniVoucher, Codego do this for crypto-general audience | Out of scope; this is a sats-native LNBits extension. Currency abstraction would require external oracle, multi-chain infrastructure | Sats only. Stated out of scope in PROJECT.md. |
| Physical card printing fulfillment | Codego ships physical cards | Requires print vendor, shipping, fulfillment ops — unrelated to this extension's purpose | Printable image/PDF generation. User prints locally. Stated out of scope in PROJECT.md. |
| Real-time everything (websocket status push) | Seems modern/expected | LNURL-w redemption is already near-instant; polling for status is sufficient for an admin dashboard; websockets add infrastructure complexity with no recipient benefit | Polling or page-refresh in issuer dashboard. Redemption page can poll for status at 2s interval to show "claimed" feedback. |

---

## Feature Dependencies

```
[LNBits Wallet / Sub-wallet]
    └──required by──> [Single Gift Card Creation]
                          └──required by──> [Bulk Card Creation (form)]
                                                └──enhanced by──> [CSV Bulk Upload]
                          └──required by──> [Redemption Flow (LNURL-w)]
                          └──required by──> [Expiration + Reclaim]

[Card Record in DB]
    └──required by──> [Issuer Dashboard]
    └──required by──> [Status Lifecycle]
    └──required by──> [Per-card Audit Log]
    └──required by──> [Cancel + Refund]

[QR Code Generation]
    └──required by──> [Card Image / Template Rendering]
                          └──required by──> [Email Delivery (image attachment)]
                          └──required by──> [Printable PDF Download]

[Email Delivery]
    └──required by──> [CSV Bulk Upload with per-recipient email]

[Design Templates]
    └──enhances──> [Card Image Rendering]
    └──enhances──> [Email Delivery]

[Single Gift Card Creation] ──conflicts──> [Partial Spend]
    (full-amount single-use is the chosen design; partial spend requires different DB schema and flow)
```

### Dependency Notes

- **Single Gift Card Creation requires LNBits sub-wallet:** Each card must fund a dedicated LNBits sub-wallet (or lock a balance claim) so the LNURL-withdraw can be served. This is the foundational unit.
- **CSV Bulk Upload requires Single Card Creation:** Bulk is N × single creation, with a preview/validation step before commit.
- **Email Delivery requires Card Image Rendering:** The email attaches the rendered card image (QR + template + amount + message). Image rendering must happen synchronously or as an async task before email send.
- **Expiry requires background task:** Expiry enforcement is not event-driven; a scheduled task (LNBits scheduler or cron) must scan for past-expiry cards and trigger reclaim.
- **Nostr delivery conflicts with simplicity:** Nostr delivery requires the extension to hold or proxy a nostr key. This should be an opt-in advanced feature, not a default requirement.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the core loop (create → deliver → redeem).

- [x] **Single gift card creation** — the atomic unit; everything else builds on this
- [x] **Fixed sats amount + optional sender name + message** — personalization is expected, low cost
- [x] **LNURL-withdraw redemption link + QR code** — the Lightning-native redemption mechanism
- [x] **Expiration date enforcement + automatic sats reclaim** — security and issuer trust
- [x] **Email delivery (image attachment)** — explicitly required in PROJECT.md; the primary distribution channel
- [x] **Issuer dashboard with card status list** — issuer must be able to see what's outstanding
- [x] **Bulk creation from form (same amount, N cards)** — low-complexity; quick win for event/holiday use
- [x] **At least 2 design templates + configurable QR placement** — makes it feel like a product, not a prototype
- [x] **API endpoint: create card, get card status** — required in PROJECT.md; enables automation

### Add After Validation (v1.x)

Features to add once core loop is validated.

- [ ] **CSV bulk upload (per-recipient variable amounts)** — high complexity; validate demand with bulk-from-form first
- [ ] **Printable PDF download** — complement email delivery; add when users request print use case
- [ ] **Per-card audit log** — add when issuers report trouble diagnosing redemption issues
- [ ] **Cancel + manual refund flow** — add when issuers report needing to invalidate cards pre-expiry

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Nostr npub delivery** — niche but aligned; defer until email delivery is stable
- [ ] **SMS delivery** — requires external provider integration; defer
- [ ] **NFC / Bolt Card integration** — physical card use case; LNBits Bolt Cards extension already exists as companion

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Single card creation + LNURL-w redemption | HIGH | LOW | P1 |
| Expiration date enforcement | HIGH | MEDIUM | P1 |
| Email delivery | HIGH | HIGH | P1 |
| Issuer dashboard | HIGH | MEDIUM | P1 |
| Design templates (2–3) | MEDIUM | MEDIUM | P1 |
| Bulk creation (same amount) | HIGH | LOW | P1 |
| API endpoints | HIGH | MEDIUM | P1 |
| CSV bulk upload (variable amounts) | HIGH | HIGH | P2 |
| Printable PDF/PNG download | MEDIUM | MEDIUM | P2 |
| Per-card audit log | MEDIUM | LOW | P2 |
| Cancel + refund | MEDIUM | MEDIUM | P2 |
| Nostr npub delivery | LOW | HIGH | P3 |
| SMS delivery | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | LNBits LNURLw (existing) | Lightning TipCards | Azteco | ZBD Vouchers | **This Extension** |
|---------|--------------------------|-------------------|--------|-------------|-------------------|
| Single card creation | ✓ (Advanced LNURLw) | ✓ | ✓ | ✓ | ✓ |
| Fixed sats amount | ✓ | ✓ | ✓ (fiat denom) | ✓ | ✓ |
| Bulk creation (same amount) | ✓ (Quick Vouchers) | ✓ (set) | ✓ (B2B) | ✓ (API) | ✓ |
| CSV bulk (variable amounts) | ✗ | ✗ | ✗ | ✗ | ✓ (v1.x) |
| Email delivery | ✗ | ✗ | ✗ (B2B portal) | ✗ (user-built) | ✓ |
| Design templates | ✗ (custom SVG only) | ✗ | ✗ | ✗ | ✓ |
| Expiry enforcement | ✗ | ✗ | ✗ | ✗ | ✓ |
| Issuer dashboard | Partial (list view) | ✓ (per-set status) | ✓ (portal) | ✓ (dashboard) | ✓ |
| Per-card status tracking | Partial | ✓ (funded/viewed/redeemed) | ✓ | ✓ | ✓ |
| Guest / walletless redemption | ✓ (instant wallet) | ✓ | ✗ | ✗ | ✓ (inherit from LNBits) |
| REST API | ✓ (LNURLw) | ✗ | ✓ (B2B) | ✓ | ✓ |
| Nostr delivery | ✗ | ✗ | ✗ | ✗ | v2+ |
| Printable PDF | Partial (QR only) | ✓ (cut-sheet print) | ✗ | ✗ | ✓ (v1.x) |
| Partial spend | ✗ | ✗ | ✗ | ✗ | ✗ (anti-feature) |

---

## Sources

- **BHN/NAPCO 2025 Digital Gift Card Programs Report** (BusinessWire, MyTotalRetail, KioskIndustry — 100 U.S. programs, 126 criteria) — industry table-stakes baseline. Confidence: MEDIUM (verified across 3 coverage sources).
- **LNBits Withdraw Extension** — https://docs.lnbits.com/extensions/withdraw/ + https://github.com/lnbits/withdraw — closest existing LNBits primitive. Confidence: LOW (web search, unverified version).
- **Lightning TipCards** — https://tipcards.io + https://github.com/Satoshi-Engineering/tipcards — LNBits-based gift/tip card reference. Confidence: LOW.
- **Azteco** — https://www.gifq.com/brands/azteco-bitcoin-voucher-lightning-gbp — Lightning voucher redemption flow. Confidence: LOW.
- **ZBD Vouchers** — https://docs.zbdpay.com/get-started/vouchers — API + email distribution pattern. Confidence: LOW.
- **btc-giftcard** — https://github.com/DanielDucuara2018/btc-giftcard — partial spend / status lifecycle reference. Confidence: LOW.
- **UniVoucher** — https://docs.univoucher.com/user-guide/bulk-creation/ — crypto bulk creation flow. Confidence: LOW.
- **Wrapped Gift Cards fraud guide** — https://wrappedgiftcards.com/guides/gift-card-fraud-prevention — security baseline. Confidence: LOW.
- **LN Gift (Lnfi Network)** — https://docs.lnfi.network/products/ln-gift — expiry, multi-claim, random/average split. Confidence: LOW.

---
*Feature research for: LNBits Gift Cards Extension*
*Researched: 2026-06-29*
