import asyncio

from loguru import logger

from lnbits.settings import settings


async def _expire_gift_cards() -> None:
    """Sweep active cards that are past their expiration and reclaim sats."""
    from .crud import get_expired_active_cards, mark_card_expired
    from .services import reclaim_card_sats

    expired = await get_expired_active_cards()
    for card in expired:
        try:
            changed = await mark_card_expired(card.id)
            if not changed:
                # Another process already transitioned this card.
                continue
            await reclaim_card_sats(card)
        except Exception as exc:
            logger.error(f"Error expiring gift card {card.id}: {exc}")


async def wait_for_expiry() -> None:
    """Periodic expiry sweep registered with create_permanent_unique_task."""
    while settings.lnbits_running:
        await _expire_gift_cards()
        await asyncio.sleep(60)
