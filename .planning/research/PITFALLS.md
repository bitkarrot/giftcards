# Pitfalls Research

**Domain:** LNBits extension for sats-denominated gift cards (creation, redemption links, QR codes, bulk CSV, email delivery, API)
**Researched:** 2026-06-29
**Confidence:** MEDIUM — findings are cross-checked across the official LNBits developer docs, LNBits core/extension source, and several public security post-mortems/gift-card security guides. Some claims (e.g., exact recommended entropy length) are de-facto standards rather than LNBits-specific mandates.

## Critical Pitfalls

Mistakes that cause rewrites, loss of funds, or major security incidents.

### Pitfall 1: Predictable or Weak Redemption Tokens

**What goes wrong:**
An attacker guesses, enumerates, or derives redemption tokens and drains unredeemed cards. In the worst case, every card in the system can be redeemed by anyone who reverse-engineers the token generation.

**Why it happens:**
Developers reuse short public IDs as secrets, seed tokens with timestamps or sequential IDs, use `Math.random()`-style PRNGs, or truncate `urlsafe_short_hash()` to make URLs prettier. LNBits provides `urlsafe_short_hash()` (a `shortuuid.uuid()`), but truncating it or using it as both public ID and secret collapses the security margin.

**How to avoid:**
- Generate redemption tokens with a cryptographically secure RNG (`secrets.token_urlsafe()`, `os.urandom()`, or the full `urlsafe_short_hash()` without truncation). Aim for **≥128 bits of entropy** for opaque URL tokens.
- Keep the token out of the database in plaintext; store a **hash** (e.g., SHA-256 of a high-entropy token) and compare with `secrets.compare_digest()` or `hmac.compare_digest()`.
- Never expose the raw token in list endpoints, admin dashboards, CSV exports, or logs.
- Add aggressive rate limiting / CAPTCHA on the public redemption endpoint from day one.

**Warning signs:**
- Token generation uses `random`, `uuid1`, `Math.random()`, timestamps, or sequential DB IDs.
- Tokens are short enough to be typed by hand (< 16 characters of base58/alphabet).
- The API returns the full token on `GET` or in exports; the link is the only secret.
- Load tests show hundreds of redemption guesses per second are possible.

**Phase to address:**
**Phase 1 — Core model & extension scaffold.** The token format is the foundation; changing it later invalidates all issued cards and links.

---

### Pitfall 2: Missing Wallet/Ownership Authorization on Admin & API Endpoints

**What goes wrong:**
Any authenticated LNBits user can create, view, or revoke gift cards in another wallet, or an attacker can enumerate cards by incrementing IDs. Because gift cards are bearer-value objects, the blast radius is direct loss of sats.

**Why it happens:**
Developers protect endpoints with `require_invoice_key` (or no decorator) when they should use `require_admin_key`, or they check the API key but forget to verify that the requested wallet/record belongs to that key. LNBits gives you the `wallet` object; you must use it to scope every read/write.

**How to avoid:**
- Use `require_admin_key` for all issuer-side mutations (create, bulk create, revoke, resend, reclaim).
- Use `require_invoice_key` only for read-only endpoints, and still filter by `wallet.id`.
- Every DB query must include a `WHERE wallet = :wallet_id` (or equivalent) check; never rely on the client sending the correct wallet ID.
- For public redemption endpoints, use only the token (no auth), but make the operation strictly single-use and idempotent.
- Validate that a gift card record exists and belongs to the caller before any update/delete.

**Warning signs:**
- `views_api.py` endpoints mix invoice/admin decorators without documented rationale.
- CRUD functions accept a `wallet_id` from the request body instead of deriving it from the authenticated wallet.
- `GET /api/v1/giftcards` returns cards for all wallets, not just the caller's.
- You can access another card by changing the ID in the URL.

**Phase to address:**
**Phase 1 — Core model & extension scaffold**, and re-audited in **Phase 5 — Admin dashboard & API hardening.**

---

### Pitfall 3: Storing or Transmitting the Raw Secret in Plaintext

**What goes wrong:**
A database leak, log leak, or email breach exposes every active gift-card code, allowing mass redemption. This is the gift-card equivalent of storing passwords in plaintext.

**Why it happens:**
The secret is needed to build the redemption URL and the QR code, so developers store it as a column in the gift-card table. Logs, exception traces, or email service integrations then capture the full URL.

**How to avoid:**
- Store only the **token hash** in the DB. Keep the original token only in memory long enough to render the QR/email once at creation time.
- Return the raw token **only** in the single-card creation response (or the generated image/email). Never return it again in any list, status, or resend endpoint.
- Mask the token in logs and exceptions; use a placeholder like `gc_*****`.
- Do not put the full token in email subject lines or plain-text SMS.
- If users need to "resend" a card, generate a new token and invalidate the old one rather than re-exposing the original.

**Warning signs:**
- The DB schema has a `token` column that stores the full URL-ready secret.
- Logs contain `https://host/giftcards/redeem?token=...`.
- CSV exports include a `token` or `link` column with live secrets.
- The admin dashboard shows a copyable redemption link.

**Phase to address:**
**Phase 1 — Core model & extension scaffold.** The data model must be designed around hashed secrets from the start.

---

### Pitfall 4: Redemption Race Conditions and Double-Spend

**What goes wrong:**
Two concurrent requests redeem the same gift card, or the card is marked redeemed before the Lightning payment to the recipient is confirmed. The issuer loses sats twice, or the recipient never receives funds while the card is burned.

**Why it happens:**
The code reads the card status, checks it, then pays, then updates status — a non-atomic window. If the payment to the recipient is asynchronous or the DB update is separate from the Lightning call, an attacker can replay the redemption request or the app can crash mid-flow.

**How to avoid:**
- Make the status transition atomic in the database: `UPDATE giftcards SET status='redeeming' WHERE status='pending' AND token_hash=:hash` and check that exactly one row was affected.
- Use DB row-level locking or an optimistic-update pattern (status + version) to prevent concurrent updates.
- Mark the card as **redeeming** before paying the recipient's invoice. Only mark **redeemed** after the Lightning payment succeeds; on failure, mark **pending** again or **failed**.
- Return an idempotency key to the recipient so a retry of the same redemption does not create a new payment.
- Use `LNbits.tasks` background workers to handle slow/outgoing payment retries without blocking the request.

**Warning signs:**
- Redemption logic is: `if card.status == 'pending': pay(); card.status = 'redeemed'`.
- No database transaction wraps the status change and the payment record insert.
- Load testing reveals duplicate successful redemptions for one card.
- The `pay_invoice` call is synchronous and can hang indefinitely.

**Phase to address:**
**Phase 3 — Redemption & payment.** This is the most dangerous operational phase.

---

### Pitfall 5: Treating the Gift Card Lifecycle as a Single Request

**What goes wrong:**
Gift cards are created and never expired/reclaimed, or expired cards remain marked as liabilities while the sats are locked in the issuer's wallet. Conversely, a card is marked expired but the recipient already paid, causing disputes.

**Why it happens:**
Developers implement creation and redemption but forget the **background lifecycle**: expiration, reclaim of unclaimed funds, and handling of Lightning payment failures/timeouts. Lightning payments are final and asynchronous; the simple request/response model does not fit.

**How to avoid:**
- Model a real state machine: `pending → redeeming → redeemed | failed → expired`.
- Register a periodic background task (`create_permanent_task`) that expires cards whose `expires_at` has passed and, if the issuer wants it, triggers a refund/return of the locked sats to the issuer's wallet.
- Do not delete expired cards; keep them for audit and support.
- Treat outgoing Lightning payments as pending until LNBits confirms settlement; do not mark the card redeemed on "payment submitted."
- Set a **safety budget** for timelocks/timeouts; follow the CertiK Lightning dApp guidance that "preimage revelation must be tightly linked to invoice settlement."

**Warning signs:**
- There is no `expires_at` column, or the column is never enforced.
- No background task is registered in `__init__.py`.
- Cards in `redeeming` status stay stuck for hours after a Lightning failure.
- The issuer has no way to reclaim sats from unredeemed cards.

**Phase to address:**
**Phase 3 — Redemption & payment** and **Phase 5 — Admin dashboard & API hardening.**

---

### Pitfall 6: Bulk CSV, Image Generation, and Email Delivery Done Synchronously

**What goes wrong:**
A bulk CSV upload of a few hundred cards times out, exhausts memory, or blocks the LNBits event loop. Email failures cause the entire batch to rollback, and the issuer has no visibility into progress.

**Why it happens:**
Developers parse the whole CSV, create every card, generate a QR image, and send an email inside the same HTTP handler. LNBits is async Python; long synchronous work (PIL/QRCODE rendering, SMTP) blocks all other requests.

**How to avoid:**
- Accept the CSV and return a **batch job ID** immediately. Enqueue the per-row work to a background task using `create_permanent_task` or the internal notification queue.
- Stream-parse the CSV and enforce a row cap (e.g., 1,000 rows per upload) and per-user rate limit.
- Generate images and send emails asynchronously. Store generated images in the DB or a static path and serve them on demand, not as inline data in the request.
- Provide a progress/status endpoint for the batch so issuers can see failures and retry individual rows.
- Validate every row: valid email/nostr npub, positive sats amount, within wallet balance, and no duplicate rows.

**Warning signs:**
- Bulk creation takes longer than a few seconds for 100 rows.
- The handler reads the entire CSV into memory and creates hundreds of Pillow/QRCODE objects in a loop.
- SMTP errors surface as 500 errors to the user and abort the whole request.
- The event loop warnings (`uvloop` warnings) appear in logs.

**Phase to address:**
**Phase 4 — Bulk CSV & delivery.**

---

### Pitfall 7: Adding New Python Dependencies or Violating Extension Rules

**What goes wrong:**
The extension cannot be installed through the official LNBits registry, or it conflicts with other extensions because tables are not namespaced. This becomes a rewrite late in the project.

**Why it happens:**
LNBits has strict extension rules: no new Python dependencies unless accepted into core `pyproject.toml` and tested with uv, poetry, and Nix; all tables must be prefixed with `ext_<id>.`; migrations must be idempotent; no core file modifications.

**How to avoid:**
- Before adding any package, search `pyproject.toml` of the target LNBits version for existing libraries (Pillow, qrcode, jinja2, etc.). Use only what is already available.
- If a new dependency is unavoidable, file an issue early and plan the full uv/poetry/nix test cycle; otherwise redesign the feature to avoid it.
- Use `Database("ext_giftcards")` and name every table `ext_giftcards.giftcards`, `ext_giftcards.redemptions`, etc.
- Make migrations idempotent: use `IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` and explicit column-add checks that work on both SQLite and PostgreSQL.
- Never ship migrations that assume a specific DB backend.

**Warning signs:**
- `requirements.txt` or `pyproject.toml` in the extension folder adds new packages.
- Table names are not prefixed with `ext_`.
- Migrations use raw SQL that fails on SQLite but works on Postgres, or vice versa.
- The extension modifies `lnbits/` core files.

**Phase to address:**
**Phase 1 — Core model & extension scaffold.**

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Store the full token in the DB so it can be re-rendered any time | Easier to resend/print cards later | DB leak = total loss; violates least privilege | **Never** for bearer-value secrets |
| Truncate `urlsafe_short_hash()` to make links short | Nicer URLs and QR codes | Predictable/guessable tokens | **Never** for redemption secrets; OK only for non-secret public IDs |
| Use the same secret for both the QR code and the redemption link | Simpler rendering | If either leaks, the card is fully compromised | Only if the entire token is always transmitted over the same secure channel; still not ideal |
| Create cards, images, and emails synchronously | Faster to implement | Timeouts, memory spikes, blocked event loop | Only in a proof-of-concept; must be async before any real load |
| Trust the client-provided `wallet_id` in the request body | Less code in the frontend | Authorization bypass | **Never** — derive wallet from the authenticated key |
| Use email address as a bearer/lookup key | Familiar UX | Email leaks or spoofing allow unauthorized access | **Never** for redemption; use opaque tokens only |
| Skip hashed-token storage for "MVP" | Faster development | Complete security rewrite later | **Never** — the data model is the hardest thing to change |
| Use `require_invoice_key` for create/bulk endpoints | Lets more clients call it | Anyone with invoice key can lock up sats | **Never** for write operations; use `require_admin_key` |

---

## Integration Gotchas

Common mistakes when connecting to LNBits core and external services.

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| LNBits API key decorators | Using `require_invoice_key` for card creation/revocation | Use `require_admin_key` for writes; use `require_invoice_key` only for reads/receiving |
| LNBits wallet object | Accepting a `wallet_id` from the request body | Derive `wallet.id` from the decorator and scope all queries to it |
| LNBits payment API | Calling `pay_invoice` synchronously without timeout or retry | Run payment in a background task; use the `Payment` model and status polling; handle `pending`/`failed` |
| LNBits invoice listener | Listening to all payments without filtering by `tag` | Always `if payment.extra.get("tag") != "ext_giftcards": return` |
| LNBits background tasks | Letting unhandled exceptions crash a permanent task | Wrap task bodies in `try/except` and log; do not re-raise |
| LNBits static files | Forgetting to register `my_extension_static_files` in `__init__.py` | Register static paths so QR images and JS assets are served |
| Email/SMTP | Sending emails synchronously and failing the whole request | Use a background queue; return a job ID; retry with exponential backoff |
| Email content | Trusting the sender message as HTML without escaping | Sanitize and escape sender-provided text; use plain text fallback |
| CSV upload | Trusting file extension and parsing with simple `split` | Use a proper CSV parser; validate headers; limit rows; sanitize fields |
| LNBits extension registry | Adding new dependencies after the feature is "done" | Check `pyproject.toml` early; design around existing libraries |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Synchronous image generation inside async handlers | Timeouts, `uvloop` warnings, CPU spikes | Offload Pillow/qrcode to a thread pool or background task; cache rendered images | > 50 cards per request or any concurrent load |
| Row-by-row INSERT in a bulk CSV loop | 10+ seconds for 500 cards, DB lock contention | Use bulk insert helpers or a single transaction; enqueue remaining work | > 100 cards per batch |
| Loading all gift cards into the frontend table | Browser freeze, huge API payload | Add pagination, search, and filters from the start | > 100 cards per wallet |
| Sending all batch emails in one handler | Memory growth, SMTP timeouts, blocked loop | Queue per-email tasks; use a background worker | > 20 emails per batch |
| No row cap on CSV upload | A 10,000-row upload can crash the server | Enforce a hard cap and rate limit per wallet | First bulk event use case |
| N+1 queries for card status and redemption history | Dashboard becomes slow as history grows | Fetch with joins or dedicated analytics query; paginate history | > 1,000 redemptions per wallet |
| Storing generated QR images as base64 in the DB | DB bloat and slow reads | Store as files or SVG in `static/` and reference by path | > 100 generated images |

---

## Security Mistakes

Domain-specific security issues beyond general OWASP basics.

| Mistake | Risk | Prevention |
|---|---|---|
| Predictable or seeded redemption tokens | Mass card draining, brute-force | CSPRNG, ≥128 bits, store hash, rate-limit, constant-time compare |
| Plaintext token storage | Total compromise on DB/log leak | Hash with SHA-256; never log or export the raw token |
| Missing ownership checks on issuer endpoints | Cross-wallet access, unauthorized revocation | Scope every query by `wallet.id`; use admin key for writes |
| Public redemption endpoint without rate limiting | Brute-force of remaining tokens | Add per-IP and per-token rate limits; consider CAPTCHA after failures |
| Trusting client-provided metadata (amount, recipient, expiry) | Over-spending, invalid emails, DoS | Validate all fields server-side; reject negative/zero sats; cap amounts |
| Logging full redemption URLs | Token exposure in log aggregation | Mask tokens in logs; use request IDs for debugging |
| Re-exposing token on resend/export | Same as plaintext storage | Generate a fresh token for resend; exports contain only status/metadata |
| No audit trail for issuance/redemption | Fraud investigation impossible | Log every create, redeem, expire, resend, and reclaim with wallet ID and timestamp |
| Email/SMS as the only bearer channel | Insecure delivery, forwarding leaks | Send short-lived HTTPS links; avoid putting the full secret in the email body |
| XSS via sender message or card template | Session theft or defacement | Escape/sanitize user-provided message and template fields |
| SSRF via callback/webhook URL (if added later) | Internal network probing | Whitelist domains and schemes; disable redirects; validate URL |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---|---|---|
| Requiring a LNBits account before redemption | Recipients abandon the gift | Allow guest redemption; optionally offer to create a wallet after redeeming |
| QR code that only works with LNBits apps | Recipients with generic scanners see a broken URL | Include a clear HTTPS landing page with a "Redeem" button and instructions |
| No visible expiration date | Recipient tries to redeem an expired card and blames the sender | Show expiration prominently on the link page, QR image, and email |
| Silent bulk CSV failures | Issuer thinks 500 cards were created; only 50 were | Return a per-row status report; surface validation errors immediately |
| No progress/status during bulk creation | Issuer refreshes the page and creates duplicates | Provide a job ID and a status endpoint; disable the submit button |
| Email-only delivery with no fallback | Emails go to spam; recipient never sees the card | Provide a printable/ downloadable QR image as a fallback |
| Tiny, low-resolution QR codes | Scanning fails at events or on printed cards | Generate high-resolution, error-corrected QR codes; test with real scanners |
| Overly complex design customization UI | Issuers spend too long designing and never send | Offer sensible default templates; advanced customization can be optional |
| Confusing "resend" vs "revoke" actions | Issuer accidentally invalidates a card | Use clear labels and confirm dialogs; explain consequences |
| No confirmation after redemption | Recipient worries whether funds arrived | Show the Lightning payment status, tx ID, and wallet instructions |

---

## "Looks Done But Isn't" Checklist

Things that appear complete in a demo but are missing critical production pieces.

- [ ] **Token generation:** Uses a CSPRNG and stores only hashes — verify with a code audit and entropy test.
- [ ] **Redemption endpoint:** Enforces rate limiting and CAPTCHA — verify with brute-force load tests.
- [ ] **Ownership checks:** Every issuer endpoint scopes queries by the authenticated wallet — verify by switching wallets in tests.
- [ ] **Atomic redemption:** Status update and payment are protected against race conditions — verify by running concurrent redemption requests.
- [ ] **Admin dashboard:** Does **not** display full tokens or reusable links — verify by inspecting API responses.
- [ ] **CSV exports:** Contain only metadata, never live tokens — verify the export file.
- [ ] **Bulk workflow:** Returns a job ID and processes image/email asynchronously — verify with a 500-row CSV.
- [ ] **Expiration:** Background task marks cards expired and supports reclaim — verify by setting short expiration windows.
- [ ] **Migrations:** Idempotent and work on both SQLite and PostgreSQL — verify by running them twice and on both backends.
- [ ] **Dependencies:** No new Python packages outside LNBits core — verify by reviewing `pyproject.toml`.
- [ ] **Audit log:** Every issuance, redemption, resend, and revocation is logged — verify by querying the audit table.
- [ ] **Email content:** Sender message is escaped and email does not leak tokens in subject lines — verify with email samples.
- [ ] **Static files:** QR images and JS assets are served through the registered static path — verify by opening the extension URL.
- [ ] **Background tasks:** Registered in `__init__.py` with `try/except` and never crash the whole app — verify by intentionally raising an error.
- [ ] **Payment failure handling:** Cards in `redeeming` status are recovered after Lightning failure — verify by failing a payment.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Token algorithm leaked / predictable | **HIGH** | Immediately invalidate all pending tokens; issue new cards with rotated tokens; notify issuers; audit redemptions for fraud |
| Missing ownership check exploited | **HIGH** | Patch endpoint; revoke unauthorized cards; add per-wallet audit review; consider rotating API keys if keys were exposed |
| Double-spend / race condition | **HIGH** | Freeze affected cards; manually reconcile Lightning payments vs. redemption records; refund or re-issue as needed |
| Bulk job crash / partial batch | **MEDIUM** | Expose per-row status; allow retry of failed rows only; do not re-create successful rows (use idempotency) |
| Dependency rejected by registry | **MEDIUM** | Refactor feature to use core libraries; if unavoidable, add dependency to LNBits core and re-test with uv/poetry/nix |
| Migration failure on upgrade | **MEDIUM** | Restore DB from backup; fix migration to be idempotent; test on both SQLite and PostgreSQL before re-deploy |
| Email provider failure | **LOW** | Provide download/print fallback; queue emails for retry; allow issuer to resend individual cards |
| Expired cards not reclaimed | **MEDIUM** | Add reclaim background job; run one-time reconciliation to return unclaimed sats to issuer wallets |
| Background task crash loop | **LOW** | Add `try/except` and restart the task; log failures; ensure crashed tasks do not stop other extension functions |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| Predictable / weak tokens | **Phase 1 — Core model & scaffold** | Code review of token generation; entropy check; test brute-force resistance |
| Missing ownership / auth checks | **Phase 1 — Core model & scaffold** | Unit tests that switch wallets and attempt cross-wallet access |
| Plaintext token storage | **Phase 1 — Core model & scaffold** | DB schema review; verify no raw token in GET/export responses |
| Race condition / double-spend | **Phase 3 — Redemption & payment** | Concurrent redemption load test; verify one success per card |
| Lifecycle / expiration / reclaim | **Phase 3 — Redemption & payment** | Set short expiration; confirm background task reclaims sats |
| Synchronous bulk/image/email | **Phase 4 — Bulk CSV & delivery** | 500-row CSV load test; verify response time < 2 s and job completes async |
| New dependencies / migration rules | **Phase 1 — Core model & scaffold** | CI check against LNBits `pyproject.toml`; migration run on SQLite + Postgres |
| Rate limiting on public endpoints | **Phase 1 & 3** | Brute-force test; confirm throttling/captcha |
| Audit logging | **Phase 5 — Admin dashboard & API hardening** | Query audit table; verify all state transitions recorded |
| Admin dashboard leaking tokens | **Phase 5 — Admin dashboard & API hardening** | Inspect API responses and UI; verify masking |

---

## Sources

- **LNBits Developer Docs — Building Extensions** (official docs): `https://docs.lnbits.com/dev/building-extensions` — covers extension structure, API decorators, migrations, dependencies, and invoice listeners. Confidence: **HIGH** (official).
- **LNBits Developer Docs — Decorators & Auth** (official docs): `https://docs.lnbits.com/dev/decorators` — details `require_admin_key`, `require_invoice_key`, and combining decorators. Confidence: **HIGH** (official).
- **LNBits Developer Docs — Background Tasks** (official docs): `https://docs.lnbits.com/dev/tasks` — patterns for `create_permanent_task`, invoice listeners, and task safety. Confidence: **HIGH** (official).
- **LNBits Payments FAQ — Hold invoices / refunds** (official docs): `https://docs.lnbits.com/guide/faq/payments` — explains Lightning finality and hold-invoice options. Confidence: **HIGH** (official).
- **LNBits Core `helpers.py`** (source): `https://raw.githubusercontent.com/lnbits/lnbits/main/lnbits/helpers.py` — shows `urlsafe_short_hash()` = `shortuuid.uuid()` and `is_valid_email_address()`. Confidence: **HIGH** (source).
- **LNBits Extension Registry Guidelines** (GitHub): `https://github.com/lnbits/lnbits-extensions` — "Do not add dependencies" and hard rules for submissions. Confidence: **HIGH** (official).
- **OopsSec Store — Insecure Randomness gift-card walkthrough** (security post-mortem): `https://koadt.github.io/oss-oopssec-store/posts/insecure-randomness-gift-card/` — concrete example of deriving gift-card codes from timestamps and LCGs. Confidence: **MEDIUM** (educational CTF, but illustrates real CWE-338).
- **Medium — How a Forged JWT Token Exposed eGift Cards** (security post-mortem): `https://codewithvamp.medium.com/how-a-forged-jwt-token-exposed-egift-cards-of-all-users-worth-millions-685f6cd20824` — token design and email-as-lookup failures. Confidence: **MEDIUM** (single-source article).
- **Tech Buzz Online — Cryptographic Gift Card Security Implementation** (guide): `https://techbuzzonline.com/guidescryptographic-gift-card-security-implementation/` — random code best practices, token storage, rate limiting. Confidence: **MEDIUM** (general guidance, not LNBits-specific).
- **CertiK — Building Secure Lightning Network dApps** (audit perspective): `https://www.certik.com/blog/building-secure-lightning-network-dapps-best-practices-and-secure-check` — preimage discipline, timelock safety budgets, atomicity, and state-machine rigor. Confidence: **MEDIUM** (high-level audit guidance).
- **Wrapped — Gift Card Fraud Prevention** (industry guide): `https://wrappedgiftcards.com/guides/gift-card-fraud-prevention` — brute-force, code harvesting, encrypted storage, per-card audit trails. Confidence: **MEDIUM** (industry best-practice).
- **GitHub — coin-gift (Lightning gift-card reference)** (open-source example): `https://github.com/antonio-ivanovski/coin-gift` — hold-invoice pattern for Lightning gifts; archived. Confidence: **MEDIUM** (reference pattern, not authoritative).
- **LNBits GitHub Security Advisory GHSA-qp8j-p87f-c8cc** (SSRF via LNURL callback): `https://github.com/lnbits/lnbits/security/advisories/GHSA-qp8j-p87f-c8cc` — reminder to validate external URLs if any callback/webhook feature is added later. Confidence: **HIGH** (official advisory).

---

*Pitfalls research for: LNBits Gift Cards extension*
*Researched: 2026-06-29*
