import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.payments import Payment, PaymentState
from lnbits.core.services.payments import update_wallet_balance, pay_invoice
from lnbits.exceptions import PaymentError
from loguru import logger

from .crud import create_card, get_card_by_token_hash
from .models import CreateGiftCard, GiftCard, CreateGiftCardResponse, GiftCardSummary


def generate_token() -> tuple[str, str]:
    """Generate a secure token and return (raw_token, token_hash)."""
    raw_token = secrets.token_urlsafe(32)  # 43 characters
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


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
