from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
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

from .crud import get_card_by_token_hash, mark_redeeming, get_cards_by_wallet
from .models import CreateGiftCard, GiftCardSummary, PublicGiftCard
from .services import create_gift_card, pay_and_complete

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
    now = card.created_at.utcnow().replace(tzinfo=card.created_at.tzinfo)
    if card.status == "expired":
        status = "expired"
    elif card.status == "redeemed":
        status = "redeemed"
    elif card.expires_at and now > card.expires_at:
        status = "expired"
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
    )


@giftcards_lnurl_router.get("/{token_hash}")
async def lnurl_params(token_hash: str, request: Request) -> LnurlWithdrawResponse:
    """LNURL-withdraw parameters endpoint."""
    card = await get_card_by_token_hash(token_hash)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found")
    
    # Check if card is active and not expired
    now = card.created_at.utcnow().replace(tzinfo=card.created_at.tzinfo)
    if card.status != "active" or (card.expires_at and now > card.expires_at):
        raise HTTPException(status_code=410, detail="Gift card is not redeemable")
    
    # Build callback URL
    callback_url = str(request.url_for("giftcards.lnurl_callback"))
    
    return LnurlWithdrawResponse(
        callback=CallbackUrl(callback_url),
        k1=token_hash,
        tag="withdrawRequest",
        minWithdrawable=MilliSatoshi(card.amount * 1000),  # Convert to millisats
        maxWithdrawable=MilliSatoshi(card.amount * 1000),  # Convert to millisats
        defaultDescription=f"Gift card {card.id[:8]}",
    )


@giftcards_lnurl_router.get("/callback")
async def lnurl_callback(
    pr: str = Query(..., description="Payment request (BOLT11 invoice)"),
    k1: str = Query(..., description="Token hash"),
) -> JSONResponse:
    """LNURL-withdraw callback endpoint."""
    # Atomically mark card as redeeming
    card = await mark_redeeming(k1)
    if not card:
        # Card already redeemed or not active
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Gift card already redeemed or not found"
            ).dict(),
        )
    
    # Try to pay the invoice
    success = await pay_and_complete(card, pr)
    
    if success:
        return JSONResponse(
            content=LnurlSuccessResponse(
                status="OK",
                reason="Gift card redeemed successfully",
            ).dict()
        )
    else:
        return JSONResponse(
            status_code=400,
            content=LnurlErrorResponse(
                reason="Payment failed. Please try again."
            ).dict(),
        )