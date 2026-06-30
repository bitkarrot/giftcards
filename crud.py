import time
from typing import Optional

from lnbits.db import Database

from .models import GiftCard, GiftCardSummary

db = Database("ext_giftcards")


async def create_card(card: GiftCard) -> GiftCard:
    await db.insert("giftcards.cards", card)
    return card


async def get_card(card_id: str) -> Optional[GiftCard]:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE id = :id",
        {"id": card_id},
        GiftCard,
    )


async def get_card_by_token_hash(token_hash: str) -> Optional[GiftCard]:
    return await db.fetchone(
        "SELECT * FROM giftcards.cards WHERE token_hash = :hash",
        {"hash": token_hash},
        GiftCard,
    )


async def get_cards_by_wallet(wallet_id: str) -> list[GiftCardSummary]:
    return await db.fetchall(
        "SELECT id, amount, status, recipient_name, sender_name, message, expires_at, created_at, redeemed_at, expired_at, redemption_url, recipient_email, email_status FROM giftcards.cards WHERE wallet = :wallet",
        {"wallet": wallet_id},
        GiftCardSummary,
    )


async def mark_redeeming(token_hash: str) -> Optional[GiftCard]:
    """Atomically mark a card as redeeming. Returns the card if successful, None if already redeemed/not active."""
    result = await db.execute(
        """
        UPDATE giftcards.cards 
        SET status = 'redeeming' 
        WHERE token_hash = :hash AND status = 'active'
        """,
        {"hash": token_hash},
    )
    
    if result.rowcount == 0:
        return None
    
    return await get_card_by_token_hash(token_hash)



async def mark_redeemed(card_id: str) -> None:
    await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'redeemed', redeemed_at = {db.timestamp_placeholder('now')}
        WHERE id = :id
        """,
        {"id": card_id, "now": time.time()},
    )


async def reset_card_to_active(card_id: str) -> None:
    """Reset a card back to active status (used when payment fails)."""
    await db.execute(
        """
        UPDATE giftcards.cards
        SET status = 'active'
        WHERE id = :id
        """,
        {"id": card_id},
    )


async def mark_card_expired(card_id: str) -> bool:
    """Atomically mark a single active card as expired. Returns True if changed."""
    result = await db.execute(
        f"""
        UPDATE giftcards.cards
        SET status = 'expired', expired_at = {db.timestamp_placeholder('now')}
        WHERE id = :id AND status = 'active'
        """,
        {"id": card_id, "now": time.time()},
    )
    return result.rowcount == 1


async def get_expired_active_cards() -> list[GiftCard]:
    """Get all active cards that have passed their expiration date."""
    return await db.fetchall(
        f"""
        SELECT * FROM giftcards.cards
        WHERE status = 'active'
        AND expires_at IS NOT NULL
        AND expires_at < {db.timestamp_placeholder('now')}
        """,
        {"now": time.time()},
        GiftCard,
    )


async def update_card_email_status(card_id: str, status: str) -> None:
    """Update the email_status column on a card."""
    await db.execute(
        """
        UPDATE giftcards.cards
        SET email_status = :status
        WHERE id = :id
        """,
        {"id": card_id, "status": status},
    )