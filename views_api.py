from datetime import datetime, timezone
import asyncio
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    mark_redeemed,
    mark_redeeming,
    reset_card_to_active,
    get_cards_by_wallet,
    count_recent_magic_links,
    get_pending_cards_by_email,
    get_magic_link_by_hash,
    mark_magic_link_used,
    mark_magic_link_used_if_unused,
    invalidate_magic_links_for_email,
    update_card_recipient_email,
    update_card_email_status,
)
from .models import (
    CreateGiftCard,
    GiftCardSummary,
    PublicGiftCard,
    ClaimRequest,
    DeliverRequest,
    BulkCreateRequest,
    CardDetailResponse,
)
from .services import (
    create_gift_card,
    bulk_create_with_funding,
    pay_and_complete,
    render_card_image,
    make_qr_png,
    generate_magic_link,
)

giftcards_api_router = APIRouter(prefix="/api/v1/cards")
giftcards_lnurl_router = APIRouter(prefix="/api/v1/lnurl")
giftcards_claim_router = APIRouter(prefix="/api/v1/claim")


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
    """Create multiple gift cards with the same sats amount.

    Per D-09 (POST /cards/bulk) and D-10 (admin key for writes).
    Builds count CreateGiftCard objects from the BulkCreateRequest
    (same amount, same metadata) and calls bulk_create_with_funding.
    """
    try:
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

    Per D-10 (invoice key for reads). Filter params (status, search,
    date_from, date_to) are accepted but filtering logic is implemented
    in Plan 03 — this plan just adds the params to the signature so the
    frontend can start sending them. Per D-12.
    """
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
        message=card.message,
        created_at=card.created_at,
        expires_at=card.expires_at,
        redeemed_at=card.redeemed_at,
        email_status=card.email_status,
        redemption_url=card.redemption_url if include_link else None,
    )


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