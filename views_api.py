from datetime import datetime, timezone
import asyncio
import hashlib
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Response
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key, require_invoice_key
from lnurl import (
    CallbackUrl,
    LnurlErrorResponse,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
    MilliSatoshi,
)
from loguru import logger
from PIL import Image, ImageDraw

from .crud import (
    get_card_by_token_hash,
    get_card,
    get_cards_by_ids,
    mark_redeemed,
    mark_redeeming,
    reset_card_to_active,
    get_cards_by_wallet,
    get_cards_by_wallet_filtered,
    count_recent_magic_links,
    get_pending_cards_by_email,
    get_magic_link_by_hash,
    mark_magic_link_used,
    mark_magic_link_used_if_unused,
    invalidate_magic_links_for_email,
    update_card_recipient_email,
    update_card_email_status,
    delete_card,
    update_card_fields,
    create_template_image,
    get_template_image,
    delete_template_image,
)
from .models import (
    CreateGiftCard,
    GiftCardSummary,
    PublicGiftCard,
    ClaimRequest,
    DeliverRequest,
    BulkCreateRequest,
    BulkDeleteRequest,
    CardDetailResponse,
    CSVRow,
    CSVValidationError,
    CSVValidationResult,
    UpdateCardRequest,
    DesignConfig,
    TemplateImage,
)
from .services import (
    create_gift_card,
    bulk_create_with_funding,
    pay_and_complete,
    render_card_image,
    make_qr_png,
    generate_magic_link,
    parse_csv,
    validate_csv_rows,
    reclaim_sats_and_delete,
    bulk_reclaim_and_delete,
    _parse_design_config,
)

giftcards_api_router = APIRouter(prefix="/api/v1/cards")
giftcards_lnurl_router = APIRouter(prefix="/api/v1/lnurl")
giftcards_claim_router = APIRouter(prefix="/api/v1/claim")


def _parse_date_to_timestamp(date_str: str) -> float:
    """Convert a date string to a UTC timestamp.

    Handles both date-only strings ("2026-01-15") and full datetime
    strings ("2026-01-15T12:00:00" or with timezone). Naive datetimes
    are assumed to be UTC.
    """
    # Date-only format: "2026-01-15" -> start of that day in UTC
    if len(date_str) == 10 and date_str.count("-") == 2:
        dt = datetime.fromisoformat(date_str + "T00:00:00+00:00")
    else:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@giftcards_api_router.post("")
async def api_create_card(
    data: CreateGiftCard,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Create a new gift card."""
    try:
        response = await create_gift_card(
            data=data,
            issuer_wallet_id=wallet.wallet.id,
            user_id=wallet.wallet.user,
            base_url=str(request.base_url),
        )
        return response.dict()
    except Exception as e:
        logger.error(f"Failed to create gift card: {e}")
        raise HTTPException(status_code=500, detail="Failed to create gift card")


@giftcards_api_router.post("/bulk")
async def api_bulk_create(
    data: BulkCreateRequest,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Create multiple gift cards — same-amount or CSV mode.

    Per D-09 (POST /cards/bulk) and D-10 (admin key for writes).
    Same-amount mode: builds count CreateGiftCard objects from count+amount.
    CSV mode (data.rows present): converts each CSVRow to a CreateGiftCard
    with per-row amounts and metadata, applies design per design_mode.
    """
    try:
        if data.rows is not None and len(data.rows) > 0:
            # CSV mode — convert CSVRow objects to CreateGiftCard objects
            rows: list[CreateGiftCard] = []
            for csv_row in data.rows:
                # Build design config per row based on design_mode
                design = None
                if data.design_mode == "shared":
                    design = data.design
                elif data.design_mode == "per_row":
                    # Build DesignConfig from CSVRow design fields
                    design_fields = {}
                    if csv_row.template_name is not None:
                        design_fields["template_name"] = csv_row.template_name
                    if csv_row.qr_x_frac is not None:
                        design_fields["qr_x_frac"] = csv_row.qr_x_frac
                    if csv_row.qr_y_frac is not None:
                        design_fields["qr_y_frac"] = csv_row.qr_y_frac
                    if csv_row.qr_size is not None:
                        design_fields["qr_size"] = csv_row.qr_size
                    if csv_row.text_x_frac is not None:
                        design_fields["text_x_frac"] = csv_row.text_x_frac
                    if csv_row.text_y_frac is not None:
                        design_fields["text_y_frac"] = csv_row.text_y_frac
                    if csv_row.font_family is not None:
                        design_fields["font_family"] = csv_row.font_family
                    if csv_row.font_size is not None:
                        design_fields["font_size"] = csv_row.font_size
                    if csv_row.font_color is not None:
                        design_fields["font_color"] = csv_row.font_color
                    if csv_row.bg_color is not None:
                        design_fields["bg_color"] = csv_row.bg_color
                    if csv_row.text_align is not None:
                        design_fields["text_align"] = csv_row.text_align
                    if design_fields:
                        design = DesignConfig(**design_fields)
                # design_mode == "none" → design stays None

                rows.append(CreateGiftCard(
                    amount=csv_row.amount_sats,
                    recipient_name=csv_row.recipient_name,
                    recipient_email=csv_row.recipient_email,
                    sender_name=csv_row.sender_name,
                    message=csv_row.message,
                    design=design,
                ))
        else:
            # Same-amount mode — build count identical CreateGiftCard objects
            rows = [
                CreateGiftCard(
                    amount=data.amount,
                    recipient_name=data.recipient_name,
                    sender_name=data.sender_name,
                    message=data.message,
                    expires_at=data.expires_at,
                    recipient_email=data.recipient_email,
                    design=data.design,
                )
                for _ in range(data.count)
            ]

        responses = await bulk_create_with_funding(
            rows=rows,
            issuer_wallet_id=wallet.wallet.id,
            user_id=wallet.wallet.user,
            base_url=str(request.base_url),
        )
        return {
            "created": len(responses),
            "card_ids": [r.card.id for r in responses],
        }
    except Exception as e:
        logger.error(f"Failed to bulk create gift cards: {e}")
        raise HTTPException(status_code=500, detail="Failed to create gift cards")


@giftcards_api_router.get("")
async def api_get_cards(
    status: str | None = Query(None),
    search: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> list[GiftCardSummary]:
    """Get all gift cards for the authenticated wallet.

    Per D-10 (invoice key for reads) and D-12 (server-side filtering).
    When any filter param (status, search, date_from, date_to) is provided,
    delegates to get_cards_by_wallet_filtered which builds a parameterized
    dynamic WHERE clause (T-03-14) with an always-present wallet isolation
    clause (T-03-15). Date strings are converted to timestamps via
    datetime.fromisoformat, handling both date-only ("2026-01-15") and
    full datetime strings.
    """
    try:
        # When called directly (e.g. in unit tests), FastAPI Query params
        # are Query objects rather than their resolved defaults. Normalize
        # non-string/non-None values to None so the filter logic works
        # correctly in both real requests and direct test calls.
        if status is not None and not isinstance(status, str):
            status = None
        if search is not None and not isinstance(search, str):
            search = None

        # Convert date strings to timestamps if provided
        date_from_ts = None
        date_to_ts = None
        if date_from is not None and isinstance(date_from, str):
            date_from_ts = _parse_date_to_timestamp(date_from)
        if date_to is not None and isinstance(date_to, str):
            date_to_ts = _parse_date_to_timestamp(date_to)

        has_filters = any(
            v is not None for v in (status, search, date_from_ts, date_to_ts)
        )
        if has_filters:
            cards = await get_cards_by_wallet_filtered(
                wallet.wallet.id,
                status=status,
                search=search,
                date_from=date_from_ts,
                date_to=date_to_ts,
            )
        else:
            cards = await get_cards_by_wallet(wallet.wallet.id)
        return cards
    except Exception as e:
        logger.error(f"Failed to get cards: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cards")


@giftcards_api_router.post("/validate-csv")
async def api_validate_csv(
    file: UploadFile = File(...),
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> CSVValidationResult:
    """Validate a CSV file and return per-row validation results.

    Per D-07 (validate before create) and D-08 (500 row max).
    Does NOT create any cards — two-phase flow.
    NOTE: This route is defined BEFORE /{card_id} routes to avoid path conflicts.
    """
    try:
        content = await file.read()
        rows = parse_csv(content)
        if len(rows) > 500:
            raise HTTPException(
                status_code=422,
                detail="CSV exceeds 500 row maximum",
            )
        valid, errors = validate_csv_rows(rows)
        return CSVValidationResult(
            valid_count=len(valid),
            error_count=len(errors),
            valid_rows=valid,
            errors=errors,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate CSV")


# ---------------------------------------------------------------------------
# Template image upload/serve/delete (m005 — bypass global asset per-user cap)
# ---------------------------------------------------------------------------

_ALLOWED_TEMPLATE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
_MAX_TEMPLATE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@giftcards_api_router.post("/template")
async def api_upload_template(
    file: UploadFile = File(...),
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Upload a custom template image to the giftcards extension's own storage.

    Bypasses the global LNbits asset system (which enforces a per-user cap
    of lnbits_max_assets_per_user, default 1) so non-admin users can upload
    and replace template images freely. Returns {"id": "<template_id>"}.
    """
    if not file.content_type or file.content_type.lower() not in _ALLOWED_TEMPLATE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Use PNG, JPEG, or WebP.",
        )

    contents = await file.read()
    if len(contents) > _MAX_TEMPLATE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {_MAX_TEMPLATE_SIZE_BYTES // 1024 // 1024}MB.",
        )

    template_id = uuid4().hex
    template = TemplateImage(
        id=template_id,
        wallet=wallet.wallet.id,
        user_id=wallet.wallet.user,
        mime_type=file.content_type,
        filename=file.filename or "template",
        size_bytes=len(contents),
        data=contents,
        created_at=datetime.now(timezone.utc),
    )
    await create_template_image(template)
    return {"id": template_id}


@giftcards_api_router.get("/template/{template_id}")
async def api_get_template(template_id: str) -> Response:
    """Serve a template image (public, no auth — needed for card rendering).

    Falls back to the global LNbits asset system for backward compatibility
    with cards created before m005 that store a global asset ID in
    template_asset_id.
    """
    template = await get_template_image(template_id)
    if template:
        return Response(
            content=template.data,
            media_type=template.mime_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f'inline; filename="{template.filename}"',
            },
        )

    # Backward compatibility: try the global asset system for old cards
    from lnbits.core.crud.assets import get_public_asset
    asset = await get_public_asset(template_id)
    if asset:
        return Response(
            content=asset.data,
            media_type=asset.mime_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f'inline; filename="{asset.name}"',
            },
        )

    raise HTTPException(status_code=404, detail="Template not found")


@giftcards_api_router.delete("/template/{template_id}")
async def api_delete_template(
    template_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Delete a template image owned by the authenticated wallet."""
    template = await get_template_image(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Template does not belong to this wallet")
    await delete_template_image(template_id)
    return {"success": True}


@giftcards_api_router.get("/public/{token_hash}")
async def api_get_public_card(token_hash: str) -> PublicGiftCard:
    """Get public card details for redemption page."""
    card = await get_card_by_token_hash(token_hash)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")
    
    # Determine status
    now = datetime.now(timezone.utc)
    if card.status == "expired":
        status = "expired"
    elif card.status == "redeemed":
        status = "redeemed"
    elif card.expires_at:
        expires = card.expires_at if card.expires_at.tzinfo else card.expires_at.replace(tzinfo=timezone.utc)
        if now > expires:
            status = "expired"
        else:
            status = "active"
    else:
        status = "active"

    return PublicGiftCard(
        status=status,
        amount=card.amount,
        sender_name=card.sender_name,
        recipient_name=card.recipient_name,
        message=card.message,
        expires_at=card.expires_at,
        expired_at=card.expired_at,
        has_design=card.template_name is not None or card.template_asset_id is not None,
    )


@giftcards_lnurl_router.get("/{token_hash}")
async def lnurl_params(
    token_hash: str, request: Request
) -> LnurlWithdrawResponse | LnurlErrorResponse:
    """LNURL-withdraw parameters endpoint."""
    card = await get_card_by_token_hash(token_hash)
    if not card:
        return LnurlErrorResponse(reason="Gift card not found")

    if card.status != "active":
        return LnurlErrorResponse(reason=f"Gift card is {card.status}")

    # Build callback URL
    callback_url = str(request.url_for("giftcards.lnurl_callback"))

    return LnurlWithdrawResponse(
        callback=CallbackUrl(callback_url, scheme=request.url.scheme),
        k1=token_hash,
        tag="withdrawRequest",
        minWithdrawable=MilliSatoshi(card.amount * 1000),
        maxWithdrawable=MilliSatoshi(card.amount * 1000),
        defaultDescription=f"Gift card {card.id[:8]}",
    )


@giftcards_lnurl_router.get("/callback", name="giftcards.lnurl_callback")
async def lnurl_callback(
    pr: str | None = None,
    k1: str | None = None,
) -> JSONResponse:
    """LNURL-withdraw callback endpoint.

    Validates the request, atomically claims the card, pays the invoice,
    and resets the card to active on any failure so the recipient can retry.
    """
    if not pr:
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Payment request is required"
            ).dict(),
        )
    if not k1:
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Redemption token is required"
            ).dict(),
        )

    # Atomically mark card as redeeming; only one concurrent request wins
    card = await mark_redeeming(k1)
    if not card:
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Gift card is not available for redemption"
            ).dict(),
        )

    try:
        await pay_and_complete(card, pr)
        await mark_redeemed(card.id)
        # Invalidate magic links for this email after redemption (D-16)
        if card.recipient_email:
            await invalidate_magic_links_for_email(card.recipient_email)
        return JSONResponse(content=LnurlSuccessResponse().dict())
    except Exception:
        # Log without exposing the raw token or internal details
        logger.exception(f"Redemption failed for gift card {card.id[:8]}")
        await reset_card_to_active(card.id)
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Redemption failed. Please try again."
            ).dict(),
        )


@giftcards_lnurl_router.get("/{token_hash}/qr")
async def lnurl_qr(token_hash: str, request: Request) -> StreamingResponse:
    """Generate QR code for LNURL-withdraw endpoint."""
    card = await get_card_by_token_hash(token_hash)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")
    
    # Check if card is active and not expired
    now = datetime.now(timezone.utc)
    if card.status != "active":
        raise HTTPException(status_code=410, detail="Gift card is not redeemable")
    if card.expires_at:
        expires = card.expires_at if card.expires_at.tzinfo else card.expires_at.replace(tzinfo=timezone.utc)
        if now > expires:
            raise HTTPException(status_code=410, detail="Gift card is not redeemable")

    # Build LNURL URL
    lnurl_url = f"{str(request.base_url).rstrip('/')}/giftcards/api/v1/lnurl/{token_hash}"
    
    # Generate QR code
    qr_img = make_qr_png(lnurl_url, size=300)
    output = BytesIO()
    qr_img.save(output, format="PNG")
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@giftcards_api_router.get("/{token_hash}/image")
async def api_card_image(token_hash: str, request: Request) -> StreamingResponse:
    """Render branded card image on demand (public, no auth).

    Returns a PNG via StreamingResponse with no-cache headers.
    """
    card = await get_card_by_token_hash(token_hash)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    lnurl_url = f"{str(request.base_url).rstrip('/')}/giftcards/api/v1/lnurl/{token_hash}"
    png_bytes = await render_card_image(card, lnurl_url, scale=1)
    output = BytesIO(png_bytes)

    return StreamingResponse(
        output,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@giftcards_api_router.get("/{card_id}/print")
async def api_card_print(
    card_id: str,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> StreamingResponse:
    """Render printable 3x-resolution branded card image (authenticated).

    Returns a PNG with Content-Disposition: attachment header.
    """
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    lnurl_url = f"{str(request.base_url).rstrip('/')}/giftcards/api/v1/lnurl/{card.token_hash}"
    png_bytes = await render_card_image(card, lnurl_url, scale=3)
    output = BytesIO(png_bytes)

    return StreamingResponse(
        output,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="giftcard_{card_id}.png"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@giftcards_api_router.get("/{card_id}")
async def api_get_card_detail(
    card_id: str,
    include_link: bool = Query(False),
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> CardDetailResponse:
    """Get detailed card info for the authenticated wallet.

    Per D-10 (invoice key for reads) and D-11 (include_link opt-in).
    redemption_url is None unless ?include_link=true is explicitly passed.
    Returns 404 if card not found, 403 if card belongs to a different wallet.
    """
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    if card.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Card does not belong to this wallet")

    return CardDetailResponse(
        card_id=card.id,
        amount=card.amount,
        status=card.status,
        recipient_name=card.recipient_name,
        sender_name=card.sender_name,
        recipient_email=card.recipient_email,
        message=card.message,
        created_at=card.created_at,
        expires_at=card.expires_at,
        redeemed_at=card.redeemed_at,
        email_status=card.email_status,
        token_hash=card.token_hash,
        redemption_url=card.redemption_url if include_link else None,
        design=_parse_design_config(card) if (card.template_name or card.template_asset_id) else None,
    )


@giftcards_api_router.put("/{card_id}")
async def api_update_card(
    card_id: str,
    data: UpdateCardRequest,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Update card metadata and design fields.

    Per D-15 — amount is NOT editable (requires cancel + recreate).
    Metadata: recipient_name, sender_name, message, recipient_email.
    Design: template selection, QR position, text styling, background color.
    Returns 404 if not found, 403 if card belongs to a different wallet.
    """
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    if card.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Card does not belong to this wallet")

    # Separate metadata fields from the optional design config.
    # The design is serialized into the qr_config / text_config JSON
    # columns plus template_name / template_asset_id, matching the
    # layout used by create_gift_card.
    updates = {}
    for field in ("recipient_name", "sender_name", "message", "recipient_email"):
        val = getattr(data, field)
        if val is not None:
            updates[field] = val

    if data.clear_design:
        updates["qr_config"] = None
        updates["text_config"] = None
        updates["template_asset_id"] = None
        updates["template_name"] = None
    elif data.design is not None:
        d = data.design
        updates["qr_config"] = json.dumps({
            "qr_x_frac": d.qr_x_frac,
            "qr_y_frac": d.qr_y_frac,
            "qr_size": d.qr_size,
        })
        updates["text_config"] = json.dumps({
            "text_x_frac": d.text_x_frac,
            "text_y_frac": d.text_y_frac,
            "font_family": d.font_family,
            "font_size": d.font_size,
            "font_color": d.font_color,
            "bg_color": d.bg_color,
            "text_align": d.text_align,
            "show_amount": d.show_amount,
            "show_recipient": d.show_recipient,
            "show_message": d.show_message,
        })
        updates["template_asset_id"] = d.template_asset_id
        updates["template_name"] = d.template_name

    if updates:
        await update_card_fields(card_id, updates)

    return {"status": "updated"}


@giftcards_api_router.delete("/bulk")
async def api_bulk_delete_cards(
    data: BulkDeleteRequest,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Delete multiple selected gift cards, reclaiming sats for active ones.

    Redeemed cards are silently skipped. Returns a summary of deleted,
    skipped, and reclaimed sats.
    """
    cards = await get_cards_by_ids(data.card_ids)
    found_ids = {card.id for card in cards}
    missing_ids = set(data.card_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Gift card(s) not found: {sorted(missing_ids)}",
        )

    wrong_wallet = [card.id for card in cards if card.wallet != wallet.wallet.id]
    if wrong_wallet:
        raise HTTPException(
            status_code=403,
            detail=f"Card(s) do not belong to this wallet: {sorted(wrong_wallet)}",
        )

    result = await bulk_reclaim_and_delete(cards)
    return {
        "status": "deleted",
        "deleted": result["deleted"],
        "skipped_redeemed": result["skipped_redeemed"],
        "reclaimed_sats": result["reclaimed_sats"],
    }


@giftcards_api_router.delete("/{card_id}")
async def api_delete_card(
    card_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Delete a gift card with sats reclaim.

    Per D-16 — hard delete with sats reclaim:
    - Active cards: reclaim sats to issuer wallet, then delete.
    - Expired cards: sats already reclaimed, just delete.
    - Redeemed cards: return 409 (cannot be deleted).
    Returns 404 if not found, 403 if card belongs to a different wallet.
    """
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    if card.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Card does not belong to this wallet")

    if card.status == "redeemed":
        raise HTTPException(status_code=409, detail="Redeemed cards cannot be deleted")

    await reclaim_sats_and_delete(card)

    return {
        "status": "deleted",
        "reclaimed_sats": card.amount if card.status == "active" else 0,
    }


# ---------------------------------------------------------------------------
# Email delivery endpoint (Phase 2 — plan 02-03)
# ---------------------------------------------------------------------------

@giftcards_api_router.post("/{card_id}/deliver")
async def api_deliver_email(
    card_id: str,
    data: DeliverRequest,
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """Trigger email delivery for a gift card.

    Updates recipient_email on the card, renders the email body (custom or fancy),
    and sends via SMTP. Updates email_status on success/failure.
    """
    from .services import send_gift_card_email

    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    # Verify card belongs to this wallet (T-02-03-09)
    if card.wallet != wallet.wallet.id:
        raise HTTPException(status_code=403, detail="Card does not belong to this wallet")

    # Update recipient email on the card
    await update_card_recipient_email(card.id, data.recipient_email)
    # H-3: sync the in-memory object so send_gift_card_email addresses the
    # NEW recipient, not the stale pre-update value.
    card.recipient_email = data.recipient_email

    # Build claim URL (the claim page, NOT the redemption link — D-12)
    claim_url = f"{str(request.base_url).rstrip('/')}/giftcards/claim"

    try:
        await send_gift_card_email(
            card=card,
            claim_url=claim_url,
            email_mode=data.email_mode,
            subject=data.subject,
            body=data.body,
            template=data.template,
            bg_color=data.bg_color,
        )
        return {"status": "sent"}
    except Exception as exc:
        # H-4: do not leak internal SMTP/exception details to the client.
        logger.warning(f"Email delivery failed for card {card.id[:8]}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Email delivery failed. Check server logs.",
        )


# ---------------------------------------------------------------------------
# Claim endpoints — magic link verification flow (Phase 2 — plan 02-03)
# ---------------------------------------------------------------------------

@giftcards_claim_router.post("")
async def api_claim_cards(data: ClaimRequest, request: Request) -> dict:
    """Public claim endpoint — accepts email, sends magic link if cards exist.

    Always returns the same response message regardless of whether cards exist
    for the email (D-14 — no email enumeration).

    Rate-limited to 3 requests per email per hour (D-13).
    """
    # Rate limit check (DB-backed, checked BEFORE generating a link)
    count = await count_recent_magic_links(data.email)
    if count >= 3:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait and try again.")

    # Find pending cards for this email
    pending = await get_pending_cards_by_email(data.email)

    if pending:
        # Generate magic link
        # Use the first card's wallet for scoping
        magic_token = await generate_magic_link(data.email, "claim_flow")
        magic_link_url = f"{str(request.base_url).rstrip('/')}/giftcards/claim/{magic_token}"

        # M-2: send the notification email via a fire-and-forget background
        # task so the response latency does not leak whether cards exist
        # (D-14 — no timing-based email enumeration). The DB row is already
        # committed, so a crash here does not lose the magic link.
        first_card = pending[0]
        claim_url = f"{str(request.base_url).rstrip('/')}/giftcards/claim"
        asyncio.create_task(
            _send_notification_safely(
                sender_name=first_card.get("sender_name") or "Anonymous",
                recipient_email=data.email,
                claim_url=claim_url,
                magic_link_url=magic_link_url,
            )
        )

    # Always return the same response (D-14 — no email enumeration)
    return {"message": "If you have pending gift cards, a verification link has been sent to your email."}


async def _send_notification_safely(
    sender_name: str,
    recipient_email: str,
    claim_url: str,
    magic_link_url: str,
) -> None:
    """Background-task wrapper that logs and swallows SMTP errors.

    The magic link row is already persisted; a delivery failure here is
    recoverable (recipient can re-request). We must never raise from a
    fire-and-forget task created via `asyncio.create_task`.
    """
    try:
        from .services import send_notification_email
        await send_notification_email(
            sender_name=sender_name,
            recipient_email=recipient_email,
            claim_url=claim_url,
            magic_link_url=magic_link_url,
        )
    except Exception as exc:
        logger.warning(f"Failed to send notification email to {recipient_email}: {exc}")


@giftcards_claim_router.get("/{magic_token}")
async def api_verify_claim(magic_token: str) -> dict:
    """Public magic link verification endpoint.

    Hashes the token, looks up the magic link, and if valid returns a list of
    pending cards with raw_tokens for redirect to the redemption page.

    Returns 404 if the token is invalid or expired.

    H-2: the single-use claim is enforced atomically via
    `mark_magic_link_used_if_unused` — the check-and-set is a single UPDATE
    that only succeeds if `used_at IS NULL`, so concurrent requests with the
    same token cannot both receive the pending cards list.
    """
    token_hash = hashlib.sha256(magic_token.encode()).hexdigest()
    link = await get_magic_link_by_hash(token_hash)
    if not link:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    # Atomically claim the link. If a concurrent request already claimed it,
    # this returns False and we refuse to hand out the cards list.
    claimed = await mark_magic_link_used_if_unused(token_hash)
    if not claimed:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    # Get pending cards for this email
    cards = await get_pending_cards_by_email(link.email)
    return {"cards": cards}