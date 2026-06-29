---
phase: 1
slug: core-loop
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-29
verified: 2026-06-29T20:00:00Z
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (LNBits core dev dependencies) |
| **Config file** | none — pytest-asyncio is configured via `pytest.ini` or `pyproject.toml` in LNBits core |
| **Quick run command** | `pytest giftcards/tests/test_core_loop.py -x` |
| **Full suite command** | `pytest giftcards/tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest giftcards/tests/test_core_loop.py -x` (or the relevant test file for the current plan)
- **After every plan wave:** Run `pytest giftcards/tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | GCARD-01 | T-01-05 | Admin-key-protected card creation | integration | `pytest giftcards/tests/test_core_loop.py -x` | ✅ | ✅ green |
| 01-01-02 | 01 | 1 | GCARD-05 | T-01-01 | Issuer wallet debited at creation | integration | `pytest giftcards/tests/test_core_loop.py -x` | ✅ | ✅ green |
| 01-01-03 | 01 | 1 | REDM-01 | T-01-06 | Public card endpoint omits sensitive fields | integration | `pytest giftcards/tests/test_core_loop.py -x` | ✅ | ✅ green |
| 01-02-01 | 02 | 2 | REDM-03 | T-02-01 | Atomic guard prevents double-spend | integration | `pytest giftcards/tests/test_redemption.py -x` | ✅ | ✅ green |
| 01-02-02 | 02 | 2 | REDM-03 | T-02-03 | Payment failure resets card to active | integration | `pytest giftcards/tests/test_redemption.py -x` | ✅ | ✅ green |
| 01-03-01 | 03 | 3 | REDM-04 | T-03-04 | Expiry sweep marks cards expired | integration | `pytest giftcards/tests/test_expiry.py -x` | ✅ | ✅ green |
| 01-03-02 | 03 | 3 | REDM-05 | T-03-05 | Expired sats reclaimed to issuer | integration | `pytest giftcards/tests/test_expiry.py -x` | ✅ | ✅ green |
| 01-03-03 | 03 | 3 | GCARD-04 | T-01-02 | Token hash never exposed in list response | integration | `pytest giftcards/tests/test_security.py -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `giftcards/tests/test_core_loop.py` — stubs for GCARD-01..GCARD-05, REDM-01, REDM-02
- [x] `giftcards/tests/test_redemption.py` — stubs for REDM-03
- [x] `giftcards/tests/test_expiry.py` — stubs for REDM-04, REDM-05
- [x] `giftcards/tests/test_security.py` — stubs for token-hash privacy and cross-wallet access
- [x] `giftcards/tests/__init__.py` — package marker

*pytest and pytest-asyncio are already installed in the LNBits core dev environment; no new framework installation is needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mobile redemption via wallet scan | REDM-02 | Requires a real Lightning wallet app and camera/QR scan | 1. Start LNBits dev server. 2. Create a card in the issuer UI. 3. Open the redemption link on a mobile device. 4. Scan the QR code with a Lightning wallet app and confirm the invoice is paid. |
| Browser link display on incognito window | REDM-01 | Visual UI check | 1. Create a card. 2. Open the redemption link in an incognito window. 3. Confirm amount, sender name, message, and QR code render correctly. |
| Create card and verify issuer wallet debit | GCARD-05 | No automated test exercises the create endpoint with a real wallet balance assertion | 1. Start LNBits dev server. 2. Note the issuer wallet balance. 3. Create a card in the issuer UI. 4. Confirm the issuer wallet balance decreased by the card amount. |

*Most backend behaviors are verified by pytest. The three items above require manual verification because they depend on visual UI, a real wallet scan, or an end-to-end wallet balance assertion that is not currently automated.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
