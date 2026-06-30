---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 3
current_phase_name: Scale & Manage
status: executing
stopped_at: Phase 3 context gathered
last_updated: "2026-06-30T07:56:00.908Z"
last_activity: 2026-06-30
last_activity_desc: Phase 02 complete, transitioned to Phase 3
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

||**Core value:** Anyone can create and redeem a sats-denominated gift card with a unique, secure redemption link.
||**Current focus:** Phase 02 — branded-delivery

## Current Position

Phase: 3 — Scale & Manage
Plan: Not started
Status: Executing Phase 02
Last activity: 2026-06-30 — Phase 02 complete, transitioned to Phase 3

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: ~25 min
- Total execution time: ~1h 15m

**By Phase:**

|| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 3 | ~25 min |
| 02 | 3 | - | - |
| 3 | 0 | TBD | - |

**Recent Trend:**

- Last 5 plans: 01-01 (completed), 01-02 (completed), 01-03 (completed)
- Trend: Phase 1 core loop complete; all 30 tests pass; post-session hardening applied.

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
- **POST-SESSION (2026-06-29): No per-card wallets** — Removed `create_card_wallet` entirely. Sats stay in the issuer wallet and are paid directly to the recipient at redemption time, following the LNbits withdraw extension pattern. Eliminates wallet proliferation (was creating 1 wallet per card). `reclaim_card_sats` now just credits the issuer wallet back.
- **POST-SESSION (2026-06-29): raw_token stored in DB** — User decision to store `raw_token` in the cards table (migration m002) so `redemption_url` can be reconstructed and displayed in the card list. Security trade-off accepted: raw_token is stored but not exposed in public/list API responses.
- **POST-SESSION (2026-06-29): Proxy headers required** — Uvicorn must be started with `--proxy-headers --forwarded-allow-ips '*'` so redemption URLs use the external domain (e.g., `https://schedulerlnbits.exe.xyz/...`) instead of `http://127.0.0.1:5000/...`.
- **POST-SESSION (2026-06-29): LNURL callback fixes** — Route needs `name="giftcards.lnurl_callback"` for `url_for`; `CallbackUrl` requires `scheme=request.url.scheme` kwarg in this version of the `lnurl` library; `expires_at` comparison must use `datetime.now(timezone.utc)` (timezone-aware) not `datetime.now()` (naive).
- **POST-SESSION (2026-06-29): Quasar v2 input binding** — `q-input` components must use `:model-value` (not `:value`) for one-way binding in Quasar v2.
- **POST-SESSION (2026-06-29): Extension icon** — Added `icon` and `tile` fields to config.json pointing to `/giftcards/static/image/giftcards.png` (128x128 PNG). Also updated `installed_extensions` table directly since the entry predated the config.json change.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2 prerequisite: Template image assets (Christmas, birthday, generic) need public-domain or original designs — source before Phase 2 begins.
- **Post-session note:** The `card_wallet_id` column remains in the DB and model (nullable, always `None` for new cards). No migration was added to drop it — this is intentional for backward compatibility with any pre-existing rows. Phase 2/3 code should not rely on `card_wallet_id` being populated.

## Deferred Items

|| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Architecture | Drop `card_wallet_id` column | Deferred | 2026-06-29 | Kept nullable for backward compat; can be dropped in a future migration if desired |

## Session Continuity

Last session: 2026-06-30T07:56:00.902Z
Stopped at: Phase 3 context gathered
Resume file: .planning/phases/03-scale-manage/03-CONTEXT.md
Next: Phase 2 — Branded Delivery (templates, email, nostr, printable download)

### Post-Session Changes (2026-06-29, outside GSD workflow)

The following changes were made after the GSD Phase 1 workflow completed, during manual testing and bug fixing:

1. **Architecture refactor**: Removed per-card wallet creation. `services.py` rewritten — `create_gift_card` debits issuer wallet directly, `pay_and_complete` pays from issuer wallet, `reclaim_card_sats` credits issuer wallet back. 10 existing card wallets deleted from DB, sats reclaimed.
2. **Migration m002**: Added `raw_token` and `redemption_url` columns to cards table.
3. **Proxy headers**: Uvicorn startup command updated with `--proxy-headers --forwarded-allow-ips '*'`.
4. **LNURL fixes**: Route name for `url_for`, `CallbackUrl` scheme kwarg, timezone-aware datetime comparison for `expires_at`.
5. **Frontend fixes**: Quasar `:model-value` binding, dialog formatting, redemption URL display in card table.
6. **Extension icon**: Added 128x128 PNG icon, updated config.json and `installed_extensions` table.
7. **DB cleanup**: Deleted 20 bad `apipayments` rows (missing `payment_hash`/`bolt11`) that caused 400 errors on wallet page load.
8. **Tests updated**: All 30 tests pass with new architecture (card_wallet_id=None in fixtures, reclaim test simplified).

All 30 tests pass. Server restarted and verified end-to-end: card creation, public endpoint, LNURL endpoint, QR endpoint all return correct responses.
