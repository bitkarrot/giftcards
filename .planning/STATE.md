---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: complete
stopped_at: Completed 01-03-PLAN.md
last_updated: "2026-06-29T19:34:00.000Z"
last_activity: 2026-06-29
last_activity_desc: Phase 1 Core Loop completed successfully
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
current_phase: 1
current_phase_name: Core Loop
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

|**Core value:** Anyone can create and redeem a sats-denominated gift card with a unique, secure redemption link.
|**Current focus:** Phase 1 — Core Loop (complete)

## Current Position

Phase: 1 of 3 (Core Loop)
Plan: 3 of 3 in current phase
Status: Phase complete — ready for verification
Last activity: 2026-06-29 — Phase 1 Core Loop completed successfully

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: ~25 min
- Total execution time: ~1h 15m

**By Phase:**

|| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 3 | ~25 min |
| 2 | 0 | TBD | - |
| 3 | 0 | TBD | - |

**Recent Trend:**

- Last 5 plans: 01-01 (completed), 01-02 (completed), 01-03 (completed)
- Trend: Phase 1 core loop complete; all 30 tests pass.

*Updated after each plan completion*
| Phase 01 P02 | 7 min | 3 tasks | 6 files |
| Phase 01-core-loop P03 | 8min | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Phase 1: Security-first — `secrets.token_urlsafe(32)` tokens, SHA-256 hash stored only; atomic `UPDATE … WHERE status = 'active'` redemption guard must be in place before any LNURL-withdraw endpoint goes live.
- Phase 1: Redemption recovery — `pay_and_complete` returns the Payment object and raises on any non-success state so the caller can reset the card to active.
- Phase 1: LNURL callback contract — validate `pr` and `k1` manually and return `LnurlErrorResponse` with a generic reason; never expose the raw token or internal stack trace.
- Phase 1: Public page callback error — the redemption page detects `?error=1` to render the error state without reloading, because the browser cannot directly observe the wallet's LNURL callback.
- Phase 1: Background expiry sweep — use `run_interval(60, _expire_gift_cards)` registered via `create_permanent_unique_task("ext_giftcards", wait_for_expiry)` for automatic crash recovery.
- Phase 1: Atomic expiry — `mark_card_expired` uses `UPDATE ... WHERE id = :id AND status = 'active'` and verifies `rowcount == 1`.
- Phase 1: Reclaim fallback — `reclaim_card_sats` credits the issuer wallet directly when no dedicated card wallet exists (D-04 fallback).
- Phase 1: Wallet balance units — `update_wallet_balance` accepts amounts in sats, not millisats; removed erroneous `*1000` and unsupported `memo` parameter from the creation flow.
- Phase 3: Redemption research flag — Lightning `pay_invoice` failure/retry handling and LNURL-withdraw walletless flow need deeper research before Phase 1 planning finalizes the redemption callback design.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2 prerequisite: Template image assets (Christmas, birthday, generic) need public-domain or original designs — source before Phase 2 begins.

## Deferred Items

|| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-29T19:34:00.000Z
Stopped at: Completed 01-03-PLAN.md
Resume file: None
Next: Phase 2 — Branded Delivery (templates, email, nostr, printable download)
