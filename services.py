import asyncio
import csv
import hashlib
import json
import secrets
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional

import pyqrcode  # type: ignore[import-untyped]
from lnbits.core.crud.assets import get_public_asset
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.payments import Payment, PaymentState
from lnbits.core.services.payments import update_wallet_balance, pay_invoice
from lnbits.exceptions import PaymentError
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError

from .crud import create_card, get_card_by_token_hash, create_magic_link, delete_card
from .models import (
    CreateGiftCard,
    GiftCard,
    CreateGiftCardResponse,
    GiftCardSummary,
    DesignConfig,
    CSVRow,
    CSVValidationError,
)

def generate_token() -> tuple[str, str]:
    """Generate a secure token and return (raw_token, token_hash)."""
    raw_token = secrets.token_urlsafe(32)  # 43 characters
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


async def generate_magic_link(email: str, wallet: str) -> str:
    """Generate a magic link for email verification and return the raw token.

    Delegates to crud.create_magic_link which stores only the SHA-256 hash.
    TTL is 30 minutes.
    """
    return await create_magic_link(email, wallet)


async def create_gift_card(
    data: CreateGiftCard, issuer_wallet_id: str, user_id: str, base_url: str
) -> CreateGiftCardResponse:
    """
    Create a gift card.

    Sats are NOT moved to a separate wallet — they stay in the issuer wallet
    and are paid directly to the recipient at redemption time, following the
    same pattern as the LNbits withdraw extension.
    """
    # Generate secure token
    raw_token, token_hash = generate_token()

    # Create card record
    card_id = f"gc_{token_hash[:16]}"

    # Serialize design config into qr_config and text_config JSON columns
    qr_config = None
    text_config = None
    template_asset_id = None
    template_name = None
    if data.design is not None:
        qr_config = json.dumps({
            "qr_x_frac": data.design.qr_x_frac,
            "qr_y_frac": data.design.qr_y_frac,
            "qr_size": data.design.qr_size,
        })
        text_config = json.dumps({
            "text_x_frac": data.design.text_x_frac,
            "text_y_frac": data.design.text_y_frac,
            "font_family": data.design.font_family,
            "font_size": data.design.font_size,
            "font_color": data.design.font_color,
            "bg_color": data.design.bg_color,
            "text_align": data.design.text_align,
            "show_amount": data.design.show_amount,
            "show_recipient": data.design.show_recipient,
            "show_message": data.design.show_message,
        })
        template_asset_id = data.design.template_asset_id
        template_name = data.design.template_name

    card = GiftCard(
        id=card_id,
        wallet=issuer_wallet_id,
        card_wallet_id=None,
        amount=data.amount,
        token_hash=token_hash,
        raw_token=raw_token,
        redemption_url=f"{base_url.rstrip('/')}/giftcards/redeem/{raw_token}",
        status="active",
        recipient_name=data.recipient_name,
        sender_name=data.sender_name,
        message=data.message,
        expires_at=data.expires_at,
        created_at=datetime.now(timezone.utc),
        redeemed_at=None,
        expired_at=None,
        template_asset_id=template_asset_id,
        template_name=template_name,
        qr_config=qr_config,
        text_config=text_config,
        recipient_email=data.recipient_email,
    )

    # Save card to database
    await create_card(card)

    # Debit issuer wallet immediately (lock the sats)
    issuer_wallet = await get_wallet(issuer_wallet_id)
    if issuer_wallet:
        await update_wallet_balance(
            wallet=issuer_wallet,
            amount=-data.amount,
        )

    # Build response
    card_summary = GiftCardSummary(
        id=card.id,
        amount=card.amount,
        status=card.status,
        recipient_name=card.recipient_name,
        sender_name=card.sender_name,
        message=card.message,
        expires_at=card.expires_at,
        created_at=card.created_at,
        redeemed_at=card.redeemed_at,
        expired_at=card.expired_at,
    )

    redemption_url = f"{base_url.rstrip('/')}/giftcards/redeem/{raw_token}"
    lnurl_url = f"{base_url.rstrip('/')}/giftcards/api/v1/lnurl/{token_hash}"

    return CreateGiftCardResponse(
        card=card_summary,
        raw_token=raw_token,
        redemption_url=redemption_url,
        lnurl_url=lnurl_url,
    )


async def bulk_create_with_funding(
    rows: list[CreateGiftCard],
    issuer_wallet_id: str,
    user_id: str,
    base_url: str,
) -> list[CreateGiftCardResponse]:
    """Create multiple gift cards by looping create_gift_card.

    Per RESEARCH.md Pattern 1 — reuse create_gift_card as the inner loop,
    do NOT write a separate batched insert. Each call generates a unique
    token, debits the issuer wallet, and inserts a DB row.

    All-or-nothing per D-07 for same-amount: if any call raises, log the
    error and re-raise. Same-amount has no per-row validation risk so
    partial failure is a safety net.
    """
    responses: list[CreateGiftCardResponse] = []
    for row in rows:
        try:
            response = await create_gift_card(
                data=row,
                issuer_wallet_id=issuer_wallet_id,
                user_id=user_id,
                base_url=base_url,
            )
            responses.append(response)
        except Exception as exc:
            logger.error(f"bulk_create_with_funding failed on row: {exc}")
            raise
    return responses


class PaymentPendingError(Exception):
    """Raised when a Lightning payment does not reach a success state."""


async def pay_and_complete(card: GiftCard, bolt11: str) -> Payment:
    """
    Pay the recipient's invoice directly from the issuer wallet.

    Raises PaymentError, PaymentPendingError, or any unexpected exception
    so the caller can reset the card to active and return a safe LNURL error.
    """
    payment = await pay_invoice(
        wallet_id=card.wallet,
        payment_request=bolt11,
        max_sat=card.amount,
        memo=f"Redeem gift card {card.id[:8]}",
    )

    if payment.status != PaymentState.SUCCESS.value:
        raise PaymentPendingError(
            f"Payment ended in {payment.status} state"
        )

    return payment


async def reclaim_card_sats(card: GiftCard) -> None:
    """Return locked sats to the issuer wallet when a card expires.

    Since sats were debited from the issuer wallet at creation time and no
    dedicated card wallet is used, we simply credit the issuer wallet back.
    """
    issuer_wallet = await get_wallet(card.wallet)
    if not issuer_wallet:
        logger.error(f"Cannot reclaim sats for expired card {card.id}: issuer wallet not found")
        return

    try:
        await update_wallet_balance(wallet=issuer_wallet, amount=card.amount)
    except Exception as exc:
        logger.error(f"Reclaim failed for expired card {card.id}: {exc}")


async def reclaim_sats_and_delete(card: GiftCard) -> None:
    """Reclaim sats (if active) and hard-delete the card record.

    Per D-16:
    - Active cards: reclaim sats to issuer wallet, then delete.
    - Expired cards: skip reclaim (sats already reclaimed by expiry task), then delete.
    - Redeemed cards: caller must reject with 409 BEFORE calling this function.
    """
    if card.status == "active":
        await reclaim_card_sats(card)
    # expired: sats already reclaimed by expiry task — skip
    # redeemed: caller rejects before reaching here
    await delete_card(card.id)


async def bulk_reclaim_and_delete(cards: list[GiftCard]) -> dict:
    """Delete a list of cards, reclaiming sats for active ones and skipping redeemed.

    Returns a summary of how many cards were deleted, how many were
    skipped because they were redeemed, and the total sats reclaimed.
    """
    deleted = 0
    skipped_redeemed = 0
    reclaimed_sats = 0
    for card in cards:
        if card.status == "redeemed":
            skipped_redeemed += 1
            continue
        if card.status == "active":
            reclaimed_sats += card.amount
        await reclaim_sats_and_delete(card)
        deleted += 1
    return {
        "deleted": deleted,
        "skipped_redeemed": skipped_redeemed,
        "reclaimed_sats": reclaimed_sats,
    }


def parse_csv(content: bytes) -> list[dict]:
    """Parse CSV bytes into a list of dicts with row_num keys.

    Uses csv.DictReader and utf-8-sig decode (strips BOM).
    Row numbering starts at 2 (row 1 is the header).
    Per RESEARCH.md — stdlib csv.DictReader, no pandas.
    """
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    rows = []
    for idx, row in enumerate(reader):
        row["row_num"] = idx + 2  # row 1 is header
        rows.append(row)
    return rows


def validate_csv_rows(rows: list[dict]) -> tuple[list[CSVRow], list[CSVValidationError]]:
    """Validate parsed CSV rows against the CSVRow Pydantic model.

    Returns (valid_rows, errors). Empty strings are cleaned to None before
    validation. Per D-07 — per-row validation, no partial create.
    """
    valid: list[CSVRow] = []
    errors: list[CSVValidationError] = []
    for row in rows:
        row_num = row.get("row_num", 0)
        # Clean empty strings to None
        cleaned = {k: (v if v != "" else None) for k, v in row.items()}
        try:
            csv_row = CSVRow(**cleaned)
            valid.append(csv_row)
        except ValidationError as exc:
            for err in exc.errors():
                field = err.get("loc", [""])[0] if err.get("loc") else ""
                errors.append(CSVValidationError(
                    row_num=row_num,
                    field=str(field),
                    message=err.get("msg", "Validation error"),
                ))
    return valid, errors


# ---------------------------------------------------------------------------
# Branded card image rendering (Phase 2)
# ---------------------------------------------------------------------------

_fonts_dir = Path(__file__).resolve().parent / "static" / "fonts"
_image_dir = Path(__file__).resolve().parent / "static" / "image"
_font_cache: dict = {}


def make_qr_png(data: str, size: int = 235, border: int = 4) -> Image.Image:
    """Generate a QR code as PNG image."""
    qr = pyqrcode.create(data)
    matrix = qr.code
    modules = len(matrix)

    total_modules = modules + border * 2
    box_size = max(1, size // total_modules)
    img_size = total_modules * box_size

    img = Image.new("RGBA", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                x0 = (x + border) * box_size
                y0 = (y + border) * box_size
                draw.rectangle(
                    [x0, y0, x0 + box_size - 1, y0 + box_size - 1],
                    fill="black",
                )

    if img_size != size:
        img = img.resize((size, size), Image.Resampling.NEAREST)

    return img


def get_font(family: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TTF font from static/fonts/ with caching."""
    key = (family, size)
    if key not in _font_cache:
        path = _fonts_dir / f"{family}.ttf"
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


def _parse_design_config(card: GiftCard) -> DesignConfig | None:
    """Parse design config from card's qr_config and text_config JSON columns.

    Returns None when the card has no template (bare QR mode).
    """
    if not card.template_name and not card.template_asset_id:
        return None

    defaults = DesignConfig()
    qr_data = {}
    text_data = {}
    if card.qr_config:
        try:
            qr_data = json.loads(card.qr_config)
        except (json.JSONDecodeError, TypeError):
            qr_data = {}
    if card.text_config:
        try:
            text_data = json.loads(card.text_config)
        except (json.JSONDecodeError, TypeError):
            text_data = {}

    return DesignConfig(
        template_asset_id=card.template_asset_id,
        template_name=card.template_name or defaults.template_name,
        qr_x_frac=qr_data.get("qr_x_frac", defaults.qr_x_frac),
        qr_y_frac=qr_data.get("qr_y_frac", defaults.qr_y_frac),
        qr_size=qr_data.get("qr_size", defaults.qr_size),
        text_x_frac=text_data.get("text_x_frac", defaults.text_x_frac),
        text_y_frac=text_data.get("text_y_frac", defaults.text_y_frac),
        font_family=text_data.get("font_family", defaults.font_family),
        font_size=text_data.get("font_size", defaults.font_size),
        font_color=text_data.get("font_color", defaults.font_color),
        bg_color=text_data.get("bg_color", defaults.bg_color),
        text_align=text_data.get("text_align", defaults.text_align),
        show_amount=text_data.get("show_amount", defaults.show_amount),
        show_recipient=text_data.get("show_recipient", defaults.show_recipient),
        show_message=text_data.get("show_message", defaults.show_message),
    )


def _generate_template_fallback(template_name: str) -> Image.Image:
    """Generate a simple fallback template if bundled assets are missing."""
    if template_name == "landscape":
        return Image.new("RGBA", (1050, 600), (245, 245, 250, 255))
    return Image.new("RGBA", (425, 650), (245, 245, 250, 255))


def _hex_to_rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Convert a #RRGGBB hex string to an (R, G, B, 255) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def _render_bare_qr_image_sync(lnurl_url: str, scale: int = 1) -> bytes:
    """Render a square bare QR image with no template or text overlay."""
    base_size = 400
    size = base_size * scale
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    qr_size = max(150, base_size - 40) * scale
    qr_img = make_qr_png(lnurl_url, size=qr_size)
    qr_x = (size - qr_img.width) // 2
    qr_y = (size - qr_img.height) // 2
    canvas.paste(qr_img, (qr_x, qr_y))
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def _render_card_image_sync(
    card: GiftCard, lnurl_url: str, scale: int = 1, template_bytes: bytes | None = None
) -> bytes:
    """Synchronous Pillow compositing: template + QR + text → PNG bytes."""
    design = _parse_design_config(card)
    if design is None:
        return _render_bare_qr_image_sync(lnurl_url, scale=scale)

    # Load template (pre-fetched asset bytes or bundled fallback)
    if template_bytes:
        template = Image.open(BytesIO(template_bytes)).convert("RGBA")
    else:
        template_name = design.template_name or "portrait"
        # For portrait/landscape, a user-supplied bg_color replaces the
        # bundled template with a solid color fill of the chosen color.
        if design.bg_color and template_name in ("portrait", "landscape"):
            fallback = _generate_template_fallback(template_name)
            template = Image.new("RGBA", fallback.size, _hex_to_rgba(design.bg_color))
        else:
            bundled = _image_dir / f"template_{template_name}.png"
            if bundled.exists():
                template = Image.open(bundled).convert("RGBA")
            else:
                template = _generate_template_fallback(template_name)

    # Scale template if needed
    if scale > 1:
        template = template.resize(
            (template.width * scale, template.height * scale),
            Image.Resampling.LANCZOS,
        )

    draw = ImageDraw.Draw(template)

    # Generate QR code at scaled size (minimum 150px)
    qr_size = max(150, design.qr_size) * scale
    qr_img = make_qr_png(lnurl_url, size=qr_size)

    # Paste QR at normalized position
    qr_x = int(design.qr_x_frac * template.width)
    qr_y = int(design.qr_y_frac * template.height)
    template.paste(qr_img, (qr_x, qr_y))

    # Draw text block (each line optional — issuer can hide amount/recipient/message)
    text_lines = []
    if design.show_amount:
        text_lines.append(f"{card.amount} sats")
    if design.show_recipient and card.recipient_name:
        text_lines.append(f"For: {card.recipient_name}")
    if design.show_message and card.message:
        text_lines.append(card.message)

    if text_lines:
        font = get_font(design.font_family, design.font_size * scale)
        anchor_map = {"left": "la", "center": "ma", "right": "ra"}
        anchor = anchor_map.get(design.text_align, "la")
        text_x = int(design.text_x_frac * template.width)
        text_y = int(design.text_y_frac * template.height)
        line_height = design.font_size * scale + 8
        for line in text_lines:
            draw.text(
                (text_x, text_y),
                line,
                fill=design.font_color,
                font=font,
                anchor=anchor,
            )
            text_y += line_height

    # Save to PNG bytes
    output = BytesIO()
    template.save(output, format="PNG")
    return output.getvalue()


async def render_card_image(card: GiftCard, lnurl_url: str, scale: int = 1) -> bytes:
    """Async wrapper that offloads Pillow rendering to a thread.

    Pre-fetches template asset bytes (if any) before offloading to thread.
    """
    design = _parse_design_config(card)
    if design is None:
        return await asyncio.to_thread(_render_bare_qr_image_sync, lnurl_url, scale)

    template_bytes = None
    if design.template_asset_id:
        try:
            asset = await get_public_asset(design.template_asset_id)
            if asset:
                template_bytes = asset.data
        except Exception as exc:
            logger.warning(f"Failed to load template asset {design.template_asset_id}: {exc}")
            template_bytes = None

    return await asyncio.to_thread(
        _render_card_image_sync, card, lnurl_url, scale, template_bytes
    )


# ---------------------------------------------------------------------------
# Email delivery (Phase 2 — plan 02-03)
# ---------------------------------------------------------------------------

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader, select_autoescape
from lnbits.settings import settings
from lnbits.helpers import is_valid_email_address

from .crud import update_card_email_status

_email_templates_dir = Path(__file__).resolve().parent / "static" / "email_templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_email_templates_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email_template(template_name: str, **context) -> str:
    """Render a Jinja2 email template with autoescape enabled."""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


def _send_smtp_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Synchronous SMTP send following the events extension pattern.

    Validates SMTP config, constructs a MIMEMultipart("alternative") message,
    and sends via smtplib.SMTP + starttls + login + sendmail.
    Called via asyncio.to_thread() from async callers.
    """
    if not settings.lnbits_email_notifications_enabled:
        raise ValueError("Email notifications are disabled")
    if not is_valid_email_address(settings.lnbits_email_notifications_email):
        raise ValueError(
            f"Invalid from email address: {settings.lnbits_email_notifications_email}"
        )
    if not is_valid_email_address(to_email):
        raise ValueError(f"Invalid email address: {to_email}")

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.lnbits_email_notifications_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    username = (
        settings.lnbits_email_notifications_username
        or settings.lnbits_email_notifications_email
    )
    with smtplib.SMTP(
        settings.lnbits_email_notifications_server,
        settings.lnbits_email_notifications_port,
    ) as smtp_server:
        smtp_server.starttls()
        smtp_server.login(username, settings.lnbits_email_notifications_password)
        smtp_server.sendmail(
            settings.lnbits_email_notifications_email,
            [to_email],
            msg.as_string(),
        )


async def send_notification_email(
    sender_name: str,
    recipient_email: str,
    claim_url: str,
    magic_link_url: str,
) -> None:
    """Send the magic link notification email (no raw_token, no card image — D-12).

    Renders notification.html template and sends via SMTP (offloaded to thread).
    """
    sender = sender_name or "Anonymous"
    subject = f"Redeem your Lightning Gift card from {sender}"
    html_body = render_email_template(
        "notification.html",
        sender_name=sender,
        claim_url=claim_url,
        magic_link_url=magic_link_url,
    )
    text_body = (
        f"Your Lightning gift card from {sender} is ready to redeem.\n\n"
        f"Click here to claim it: {magic_link_url}\n\n"
        f"This link expires in 30 minutes."
    )
    await asyncio.to_thread(
        _send_smtp_email, recipient_email, subject, text_body, html_body
    )


async def send_gift_card_email(
    card: GiftCard,
    claim_url: str,
    email_mode: str,
    subject: str | None = None,
    body: str | None = None,
    template: str | None = None,
    bg_color: str | None = None,
) -> None:
    """Orchestrate email delivery for a gift card.

    Renders the email body based on mode (custom or fancy), sends via SMTP
    (offloaded to thread), and updates email_status on the card record.
    """
    sender = card.sender_name or "Anonymous"
    subj = subject or f"You have a gift card from {sender}"

    if email_mode == "fancy":
        html_body = render_email_template(
            "fancy.html",
            sender_name=sender,
            message=card.message or "",
            claim_url=claim_url,
            amount=card.amount,
            bg_color=bg_color or "#1976d2",
        )
        text_body = (
            f"You have a gift card from {sender}.\n\n"
            f"Amount: {card.amount} sats\n"
            f"Message: {card.message or ''}\n\n"
            f"Claim your gift card: {claim_url}"
        )
    else:
        # Custom text mode
        custom_body = body or ""
        html_body = render_email_template(
            "custom_text.html",
            body=custom_body,
            claim_url=claim_url,
        )
        text_body = f"{custom_body}\n\nClaim your gift card: {claim_url}"

    try:
        await asyncio.to_thread(
            _send_smtp_email,
            card.recipient_email,
            subj,
            text_body,
            html_body,
        )
        await update_card_email_status(card.id, "sent")
    except Exception as exc:
        logger.warning(f"Email delivery failed for card {card.id[:8]}: {exc}")
        await update_card_email_status(card.id, "failed")
        raise
