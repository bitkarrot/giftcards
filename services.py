import hashlib
import secrets
from datetime import datetime
from typing import Optional

from fastapi import Request
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models.payments import Payment, PaymentState
from lnbits.core.models.wallets import WalletType
from lnbits.core.services.payments import update_wallet_balance, pay_invoice
from lnbits.exceptions import PaymentError
from loguru import logger

from .crud import (
    create_card,
    get_card_by_token_hash,
    mark_expired,
    get_expired_active_cards,
)
from .models import CreateGiftCard, GiftCard, CreateGiftCardResponse, GiftCardSummary


def generate_token() -> tuple[str, str]:
    """Generate a secure token and return (raw_token, token_hash)."""
    raw_token = secrets.token_urlsafe(32)  # 43 characters
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


async def create_card_wallet(user_id: str, card_id: str) -> Optional[str]:
    """
    Create a dedicated wallet under the issuer user to hold locked sats.
    Returns wallet ID or None if creation fails.
    """
    try:
        wallet = await create_wallet(
            user_id=user_id,
            wallet_name=f"GiftCard {card_id[:8]}",
            wallet_type=WalletType.LIGHTNING,
        )
        return wallet.id
    except Exception as e:
        logger.warning(f"Could not create card wallet for {card_id}: {e}")
        return None


async def create_gift_card(
    data: CreateGiftCard, issuer_wallet_id: str, user_id: str, base_url: str
) -> CreateGiftCardResponse:
    """
    Create a funded gift card by debiting the issuer wallet.
    """
    # Generate secure token
    raw_token, token_hash = generate_token()
    
    # Create card record first
    card_id = f"gc_{token_hash[:16]}"
    
    # Try to create dedicated card wallet (D-03)
    card_wallet_id = await create_card_wallet(user_id, card_id)
    
    card = GiftCard(
        id=card_id,
        wallet=issuer_wallet_id,
        card_wallet_id=card_wallet_id,
        amount=data.amount,
        token_hash=token_hash,
        status="active",
        recipient_name=data.recipient_name,
        sender_name=data.sender_name,
        message=data.message,
        expires_at=data.expires_at,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
    )
    
    # Save card to database
    await create_card(card)
    
    # Debit issuer wallet (D-03)
    issuer_wallet = await get_wallet(issuer_wallet_id)
    if issuer_wallet:
        await update_wallet_balance(
            wallet=issuer_wallet,
            amount=-data.amount * 1000,  # Convert to millisats
            memo=f"Gift card {card_id[:8]} created",
        )
    
    # Credit card wallet if created (D-03)
    if card_wallet_id:
        card_wallet = await get_wallet(card_wallet_id)
        if card_wallet:
            await update_wallet_balance(
                wallet=card_wallet,
                amount=data.amount * 1000,  # Convert to millisats
                memo=f"Funding for gift card {card_id[:8]}",
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
    Pay the recipient's invoice and return the resulting Payment.

    Raises PaymentError, PaymentPendingError, or any unexpected exception
    so the caller can reset the card to active and return a safe LNURL error.
    """
    # Use card wallet if available, otherwise use issuer wallet (D-04 fallback)
    wallet_id = card.card_wallet_id or card.wallet
    wallet = await get_wallet(wallet_id)

    if not wallet:
        raise Exception(f"Wallet {wallet_id} not found")

    payment = await pay_invoice(
        wallet_id=wallet_id,
        payment_request=bolt11,
        memo=f"Redeem gift card {card.id[:8]}",
    )

    if payment.status != PaymentState.SUCCESS.value:
        raise PaymentPendingError(
            f"Payment ended in {payment.status} state"
        )

    return payment


async def expire_gift_cards() -> None:
    """
    Background task to expire cards and reclaim sats to issuer.
    """
    expired_cards = await get_expired_active_cards()
    
    for card in expired_cards:
        try:
            # Mark as expired
            await mark_expired(card.id)
            
            # Reclaim sats to issuer wallet
            if card.card_wallet_id:
                # Get wallets
                card_wallet = await get_wallet(card.card_wallet_id)
                issuer_wallet = await get_wallet(card.wallet)
                
                if card_wallet and issuer_wallet:
                    # Transfer from card wallet back to issuer
                    await update_wallet_balance(
                        wallet=card_wallet,
                        amount=-card.amount * 1000,  # Convert to millisats
                        memo=f"Expire gift card {card.id[:8]}",
                    )
                    await update_wallet_balance(
                        wallet=issuer_wallet,
                        amount=card.amount * 1000,  # Convert to millisats
                        memo=f"Reclaim expired gift card {card.id[:8]}",
                    )
            else:
                # If no dedicated wallet, sats are already with issuer
                logger.info(f"Gift card {card.id[:8]} expired (no dedicated wallet)")
                
        except Exception as e:
            logger.error(f"Failed to expire gift card {card.id[:8]}: {e}")