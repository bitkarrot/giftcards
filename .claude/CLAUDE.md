<!-- GSD:project-start source:PROJECT.md -->

## Project

**LNBits Gift Cards Extension**

An LNBits extension that lets wallet holders create, customize, distribute, and redeem Bitcoin Lightning gift cards denominated in sats. Gift cards can be designed individually or in bulk, delivered as unique redemption links or printable/scannable QR images, and expired automatically if not claimed.

**Core Value:** Anyone can create and redeem a sats-denominated gift card with a unique, secure redemption link.

### Constraints

- **Tech stack**: Must be built as an LNBits extension, matching the runtime version and conventions of the target LNBits installation.
- **Security**: Redemption links/tokens must be unguessable and single-use (or idempotent for the intended recipient).
- **Compatibility**: Must work alongside existing LNBits wallet and account system without breaking core flows.
- **Performance**: Bulk creation of hundreds of cards should be responsive; image generation should not block the request thread.
- **Privacy**: Recipient email/nostr npub is stored only as needed for delivery and should not be exposed publicly.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LNBits runtime (Python) | 3.10–3.12 (`requires-python >=3.10,<3.13`) | Extension runtime | The target LNBits installation in this workspace is v1.5.4; extensions must match the core Python constraint. |
| FastAPI | `~0.116.1` | Extension HTTP API / router | LNBits core is a FastAPI application; extensions are registered as `APIRouter` instances. |
| Starlette | `~0.47.1` | ASGI request/response layer | Core dependency that FastAPI is built on. |
| Pydantic | `~1.10.26` | Request/response models and validation | LNBits 1.5.x still uses Pydantic v1; extension models must be compatible. |
| SQLAlchemy + asyncpg / aiosqlite | `~1.4.54` / `~0.31.0` / `~0.22.1` | Database access | `lnbits.db.Database` abstracts these; supports SQLite (dev) and PostgreSQL (prod). |
| Jinja2 | `~3.1.6` | HTML templating | Used for public redemption pages and any extension-rendered UI. |
| Vue 3 + Quasar | bundled in LNBits core | Issuer dashboard and redemption pages | Official LNBits frontend stack; extensions ship `static/js/*.vue` + `*.js` files. |
| Uvicorn / asyncio | `~0.40.0` | ASGI server / async runtime | Used by LNBits core; no extension server needed. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | `~12.1.0` | Gift card image composition, QR overlay, template scaling | Always for image generation. |
| pyqrcode | `~1.2.1` | QR code matrix generation | Always for QR codes; draw the matrix with Pillow. |
| python-multipart | `~0.0.22` | CSV file upload handling | For bulk CSV import endpoint via `fastapi.UploadFile`. |
| httpx | `~0.27.2` | Internal HTTP client | For inter-extension calls (e.g., fetching asset data or other extension APIs). |
| lnurl | `~0.10.0` | LNURL-withdraw redemption (optional future) | Add later if you want native wallet scan-to-redeem without a web page. |
| bolt11 | `~2.1.1` | Decode/validate Lightning invoices | If redemption collects a bolt11 invoice from the recipient. |
| `lnbits.core.services.payments` | core | Pay invoices / create invoices | Use `pay_invoice` to send sats when a card is redeemed; `create_payment_request` for funding tests. |
| `lnbits.core.services.assets` + `lnbits.core.crud.assets` | core | Store uploaded gift card templates | Use `create_user_asset` for uploads and `get_public_asset` for retrieval. |
| `smtplib` + `email.mime` | stdlib | Email delivery with image attachments | Use LNBits core SMTP settings; build the message with `MIMEMultipart` + `MIMEImage`. |
| `secrets` + `hashlib` | stdlib | Secure redemption token generation and hashing | Generate `secrets.token_urlsafe(32)`; store a SHA-256 hash. |
| `csv` | stdlib | Parse bulk CSV uploads | No external CSV parser needed. |
| `asyncio` | stdlib | Background fire-and-forget tasks | Use `asyncio.create_task` for email/image generation; `asyncio.to_thread` for CPU-bound Pillow work. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| black | Python formatting | Match LNBits core line length of 88. |
| ruff | Python linting | Use the same rule set as the events extension. |
| mypy | Type checking | Enable the Pydantic plugin. |
| pytest + pytest-asyncio | Testing | Async tests for FastAPI endpoints. |
| pre-commit | Git hooks | Same as the events extension. |
| prettier | JS/Vue formatting | Optional; the events extension uses it in `package.json`. |

## Installation

# Extension runtime: NO additional Python packages are needed beyond LNBits core.

# The extension only declares "lnbits>1" as its dependency.

# Install LNBits core locally (or use the existing virtual environment):

# Dev dependencies (match the events extension reference):

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pyqrcode` + Pillow | `qrcode` + Pillow | Use `qrcode` only if LNBits upstream adds it; it has more styling options, but it is not in the core dependency set today. |
| URL-based redemption page | LNURL-withdraw (`lnurl` package) | Use LNURL-withdraw once you want native wallet scan-to-redeem without a web page. |
| PNG gift card images | Server-side PDF (`reportlab` / `img2pdf`) | Use PDF only if a new dependency is accepted upstream; otherwise generate a high-resolution PNG and let the browser print to PDF. |
| LNBits core SMTP settings | Custom extension SMTP settings | Use custom settings only if the extension needs a separate sender identity from the LNBits instance. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Pydantic v2 | LNBits 1.5.x uses Pydantic v1; mixing v2 breaks model serialization and validation. | Pydantic `~1.10.26` |
| Flask / Quart / Django | Extensions must be FastAPI routers registered by LNBits. | FastAPI `APIRouter` |
| New runtime dependencies in the extension | LNBits policy discourages them; upstream acceptance is uncertain and may block distribution. | Core packages listed above. If none fit, open a core issue first. |
| `pandas` for CSV parsing | Heavy dependency; the stdlib `csv` module is sufficient for the bulk-import format. | `csv.DictReader` |
| Server-side PDF generation libraries | `reportlab` and `img2pdf` are not in core; adding them violates the dependency policy. | PNG + browser print / CSS print media. |
| External QR or image generation APIs | Latency, cost, privacy, and offline-card requirements make external APIs unsuitable. | Pillow + pyqrcode |
| Celery / RQ / Redis queues | LNBits already runs on asyncio; no extra queue infrastructure is needed. | `asyncio.create_task` or `lnbits.tasks.create_permanent_unique_task` |
| `uuid4` or `urlsafe_short_hash` as redemption secrets | Not designed for long-lived bearer tokens; they may be too short or not CSPRNG-backed. | `secrets.token_urlsafe(32)` |
| Storing plaintext redemption tokens in the database | A database leak would compromise all unclaimed cards. | Store a SHA-256 hash of the token; display the token only once during creation/email. |
| Client-side-only QR generation | Cannot produce reliable image attachments for email or printable cards. | Server-side Pillow rendering |
| Core `send_email_notification` for image attachments | It does not support attachments; it only sends plain/html text. | Build a custom `MIMEMultipart` message that reuses LNBits core SMTP settings. |

## Stack Patterns by Variant

- Debit the issuer's wallet via `pay_invoice` (or hold the amount as a pending payment) and generate a unique token.
- Compose the card image on demand with Pillow + pyqrcode and return it immediately or attach it to an email.
- Generate the card image in a background `asyncio.create_task` so the creation endpoint stays responsive.
- Use `MIMEMultipart("mixed")` with `MIMEImage` to attach the PNG.
- Reuse `settings.lnbits_email_notifications_*` for the SMTP server, port, and credentials.
- Expose a public endpoint that returns the composed PNG image (e.g., `/giftcards/api/v1/cards/{id}/image`).
- Add `Cache-Control: no-cache, no-store, must-revalidate` headers because the image contains a bearer token.
- Provide a redemption page with a CSS print stylesheet as an alternative to pure image printing.
- Accept the file via `fastapi.UploadFile` (python-multipart handles multipart parsing).
- Parse with `csv.DictReader` and validate each row with a Pydantic model.
- Queue per-card image and email generation asynchronously so the request can return a summary immediately.
- Implement an LNURL-withdraw flow using the `lnurl` package already in core.
- Keep the existing URL-based redemption page as a fallback for wallets that do not support LNURL.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `pydantic ~1.10.26` | `fastapi ~0.116.1` | Required by LNBits core. |
| `pillow ~12.1.0` | `pyqrcode ~1.2.1` | QR is generated as a matrix and drawn with Pillow. |
| `sqlalchemy ~1.4.54` | `asyncpg ~0.31.0` / `aiosqlite ~0.22.1` | Both drivers supported by `lnbits.db.Database`. |
| `python-multipart ~0.0.22` | `fastapi ~0.116.1` | Used for CSV upload. |
| `lnbits>1` | extension `pyproject.toml` | Extension dependency on the core package. |

## Sources

- LNBits core `pyproject.toml` v1.5.4 (`/home/exedev/lnbits/pyproject.toml`) — dependency versions and Python constraint.
- LNBits docs / Building Extensions (`https://docs.lnbits.com/dev/building-extensions`) — extension structure, FastAPI routers, frontend, and dependency policy.
- LNBits `lnbits/extensions/events` (`/home/exedev/lnbits/lnbits/extensions/events`) — reference implementation for QR generation, image composition, email notifications, database migrations, and Vue frontend.
- LNBits core `lnbits/core/services/payments.py` — `pay_invoice` and `create_payment_request` primitives.
- LNBits core `lnbits/core/services/notifications.py` — SMTP settings and core email helpers.
- LNBits core `lnbits/core/services/assets.py` and `lnbits/core/crud/assets.py` — template image upload and retrieval.
- Python standard library documentation — `secrets`, `hashlib`, `csv`, `smtplib`, `email.mime`.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
