---
status: pending
phase: 02-branded-delivery
source: [02-VERIFICATION.md]
started: 2026-06-30T04:37:28Z
updated: 2026-07-01T05:20:00Z
---

## Current Test

[post-session additions pending human verification]

## Tests

### 1. Interactive card designer UX (drag/resize/styling in browser)
expected: Open the create dialog in a browser and interact with the card designer — drag QR, drag text, resize QR, change font/size/color/alignment, select portrait/landscape/custom upload. All drag/resize/styling controls respond smoothly; QR cannot be resized below 150px; custom upload triggers file picker and loads image as preview background. An info banner explains drag/resize interactions.
result: pass (2026-06-30)

### 2. Background color picker for Portrait/Landscape templates
expected: Select Portrait or Landscape template and pick a background color using the color picker. The card preview shows a solid background color instead of the template image. The bg_color is persisted and the server-rendered card image uses the solid color fill.
result: pending

### 3. Visual branded card rendering on redemption page (with bg_color)
expected: Create a card with a design config (including bg_color) and open the redemption page in a browser. The branded card image (with bg_color fill + QR + text) renders on the redemption page; Phase 1 cards without design show the bare QR fallback.
result: pass (2026-06-30 — without bg_color; re-verify with bg_color)

### 4. Printable PNG download
expected: Click "Download PNG" in the card list expanded row. A 3x-resolution PNG file downloads with filename giftcard_{card_id}.png.
result: pass

### 5. Email background color picker (Fancy HTML mode)
expected: Open the "Send Gift Card Email" dialog, select "Fancy HTML Template" mode, and pick a background color. A background color picker appears in fancy mode. The email preview updates live with the chosen color (header, message border, CTA button). The sent email uses the chosen bg_color.
result: pending

### 6. End-to-end email delivery with configured SMTP
expected: Visit /giftcards/claim, enter an email, and verify the full magic link flow end-to-end with SMTP configured. Email entry → "Check Your Email" confirmation → receive notification email → click magic link → see pending cards list → click Redeem → redirect to redemption page.
result: pass

### 7. Rate limiting (429 on 4th request)
expected: Request 4 magic links for the same email within an hour. 4th request returns 429 "Too Many Requests" and the claim page shows the rate-limited state.
result: pass

### 8. Post-redemption magic link invalidation
expected: Redeem a card and then revisit the magic link URL. Magic link shows "Link Invalid or Expired" — invalidated after redemption (D-16).
result: pass

### 9. Card design section layout (single-column, no cutoff)
expected: Verify the card design section layout in all dialogs (create, bulk same-amount, bulk CSV, edit). The card design section uses a single-column layout — preview and controls stack vertically, no elements are cut off. An info banner below the "Card Design" heading explains drag/resize.
result: pending

## Summary

total: 9
passed: 5
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

- Test 2 (bg_color picker): new feature, requires manual browser verification
- Test 3 (branded card with bg_color): previously passed without bg_color; needs re-verification with bg_color enabled
- Test 5 (email bg_color): new feature, requires manual browser + SMTP verification
- Test 9 (single-column layout): new fix, requires manual browser verification
