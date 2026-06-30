from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key
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
    mark_redeemed,
    mark_redeeming,
    reset_card_to_active,
    get_cards_by_wallet,
)
from .models import CreateGiftCard, GiftCardSummary, PublicGiftCard
from .services import create_gift_card, pay_and_complete, render_card_image, make_qr_png

giftcards_api_router = APIRouter(prefix="/api/v1/cards")
giftcards_lnurl_router = APIRouter(prefix="/api/v1/lnurl")


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


@giftcards_api_router.get("")
async def api_get_cards(
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> list[GiftCardSummary]:
    """Get all gift cards for the authenticated wallet."""
    try:
        cards = await get_cards_by_wallet(wallet.wallet.id)
        return cards
    except Exception as e:
        logger.error(f"Failed to get cards: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cards")


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