# Phase 1: Core Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 1-Core Loop
**Areas discussed:** Redemption mechanism, Funding model, Token security, State machine, Expiry/reclaim, API/auth, Database

---

## Redemption mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| LNURL-withdraw | Recipient wallet pulls sats via BOLT11 invoice; guest/walletless friendly | ✓ |
| Direct BOLT11 payment | Issuer pays a provided invoice at redemption time | |

**User's choice:** Auto-selected recommended option (LNURL-withdraw).
**Notes:** Chosen because it is the Lightning-native pull model, avoids failed pushes, and matches the existing LNBits withdraw extension pattern. The web link displays the card; the QR encodes the LNURL-withdraw endpoint using the token hash.

---

## Funding model

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated extension wallet | Issuer wallet is debited at creation; sats held in a per-issuer extension wallet | ✓ |
| Balance claim in DB | Issuer wallet is debited at creation conceptually; actual payout happens later | |

**User's choice:** Auto-selected recommended option (dedicated extension wallet).
**Notes:** This satisfies the requirement that the issuer wallet is debited at creation and provides clean accounting for redemption and reclaim.

---

## Token security

| Option | Description | Selected |
|--------|-------------|----------|
| `secrets.token_urlsafe(32)` + SHA-256 hash | 256-bit raw token generated once; only hash stored | ✓ |
| UUID4 or short hash | Simpler but weaker or guessable | |

**User's choice:** Auto-selected recommended option (CSPRNG + hash storage).
**Notes:** This is the highest-security option and aligns with research warnings about predictable tokens.

---

## Card state machine

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal states | created → active → redeemed / expired | ✓ |
| Full lifecycle | created → active → pending → redeeming → redeemed / failed / expired / cancelled | |

**User's choice:** Auto-selected recommended option (minimal states).
**Notes:** The `cancelled` and `redeeming_failed` states are deferred to later phases. Phase 1 needs only the core loop.

---

## Expiry and reclaim

| Option | Description | Selected |
|--------|-------------|----------|
| `create_permanent_unique_task` periodic sweep | Background task scans expired cards and reclaims sats | ✓ |
| Scheduler/cron external to LNBits | Requires external infrastructure | |

**User's choice:** Auto-selected recommended option (LNBits background task).
**Notes:** 1-minute interval is acceptable for Phase 1. Tighter scheduling is deferred.

---

## API and auth

| Option | Description | Selected |
|--------|-------------|----------|
| Admin key for issuer endpoints | Create and list endpoints require `require_admin_key` | ✓ |
| Invoice key for list | List endpoints use `require_invoice_key` for broader access | |

**User's choice:** Auto-selected recommended option (admin key for all issuer endpoints).
**Notes:** Invoice-key access is deferred to Phase 3 (API hardening). Public redemption endpoints remain unauthenticated.

---

## Database

| Option | Description | Selected |
|--------|-------------|----------|
| `ext_giftcards` namespace with token hash index | Follows LNBits extension conventions; unique indexed token hash | ✓ |
| Generic table names | Simpler but risks collisions | |

**User's choice:** Auto-selected recommended option (namespaced tables with indexed hash).
**Notes:** Follows the events extension pattern and LNBits extension rules.

---

## Claude's Discretion

- Exact URL path naming for redemption and LNURL endpoints.
- Pydantic v1 model field names and validators.
- Specific DB column types and indexes.
- Detailed failure-recovery state transitions for `pay_invoice` errors.

## Deferred Ideas

- Cancel + manual refund flow (v2).
- Per-card audit log (v2).
- Printable/PDF generation (Phase 2).
- Email/nostr delivery (Phase 2).
- Bulk creation and REST API (Phase 3).
- Issuer dashboard (Phase 3).
- Rate limiting (Phase 6).
