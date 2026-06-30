---
status: complete
phase: 02-branded-delivery
source: [02-VERIFICATION.md]
started: 2026-06-30T04:37:28Z
updated: 2026-06-30T06:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Interactive card designer UX (drag/resize/styling in browser)
expected: Open the create dialog in a browser and interact with the card designer — drag QR, drag text, resize QR, change font/size/color/alignment, select portrait/landscape/custom upload. All drag/resize/styling controls respond smoothly; QR cannot be resized below 150px; custom upload triggers file picker and loads image as preview background.
result: pass

### 2. Visual branded card rendering on redemption page
expected: Create a card with a design config and open the redemption page in a browser. The branded card image (template + QR + text) renders on the redemption page; Phase 1 cards without design show the bare QR fallback.
result: pass

### 3. Printable PNG download
expected: Click "Download PNG" in the card list expanded row. A 3x-resolution PNG file downloads with filename giftcard_{card_id}.png.
result: pass

### 4. End-to-end email delivery with configured SMTP
expected: Visit /giftcards/claim, enter an email, and verify the full magic link flow end-to-end with SMTP configured. Email entry → "Check Your Email" confirmation → receive notification email → click magic link → see pending cards list → click Redeem → redirect to redemption page.
result: pass

### 5. Rate limiting (429 on 4th request)
expected: Request 4 magic links for the same email within an hour. 4th request returns 429 "Too Many Requests" and the claim page shows the rate-limited state.
result: pass

### 6. Post-redemption magic link invalidation
expected: Redeem a card and then revisit the magic link URL. Magic link shows "Link Invalid or Expired" — invalidated after redemption (D-16).
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
