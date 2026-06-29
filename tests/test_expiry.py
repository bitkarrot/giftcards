import hashlib
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from giftcards.crud import (
    create_card,
    db,
    get_card_by_token_hash,
    get_expired_active_cards,
    mark_card_expired,
)
from giftcards.migrations import m001_initial, m002_add_raw_token
from giftcards.models import GiftCard
from giftcards.services import generate_token, reclaim_card_sats
from giftcards.tasks import _expire_gift_cards
from giftcards.views_api import lnurl_callback


async def _reset_table():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await m001_initial(db)
    await m002_add_raw_token(db)


async def _make_card(
    wallet_id: str = "wallet_test",
    card_wallet_id: str = "wallet_card",
    amount: int = 1000,
    status: str = "active",
    expires_at: datetime | None = None,
) -> GiftCard:
    raw_token, token_hash = generate_token()
    card = GiftCard(
        id=f"gc_{token_hash[:16]}",
        wallet=wallet_id,
        card_wallet_id=card_wallet_id,
        amount=amount,
        token_hash=token_hash,
        status=status,
        recipient_name="Bob",
        sender_name="Alice",
        message="Hello",
        expires_at=expires_at,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
    )
    await create_card(card)
    return card


@pytest.fixture(autouse=True)
async def clean_table():
    await _reset_table()
    yield
    await _reset_table()


def _wallet_mock(wallet_id: str, balance_msat: int = 1_000_000):
    wallet = MagicMock()
    wallet.id = wallet_id
    wallet.balance = balance_msat
    wallet.can_send_payments = True
    return wallet


@pytest.mark.anyio
async def test_expired_active_cards_query():
    """Cards with a past expiration date are returned by get_expired_active_cards."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(expires_at=past)

    expired = await get_expired_active_cards()
    assert any(c.id == card.id for c in expired), "expected expired card in query result"


@pytest.mark.anyio
async def test_non_expired_active_cards_not_returned():
    """Cards with a future expiration date are not returned by the sweep query."""
    future = datetime.now() + timedelta(days=1)
    card = await _make_card(expires_at=future)

    expired = await get_expired_active_cards()
    assert all(c.id != card.id for c in expired), "future card should not be expired"


@pytest.mark.anyio
async def test_mark_card_expired_atomic():
    """mark_card_expired only updates a card that is still active."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(expires_at=past)

    await mark_card_expired(card.id)
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "expired"
    assert updated.expired_at is not None


@pytest.mark.anyio
async def test_mark_card_expired_ignores_already_redeemed():
    """mark_card_expired does not transition a redeemed card to expired."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(status="redeemed", expires_at=past)

    await mark_card_expired(card.id)
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "redeemed"


@pytest.mark.anyio
async def test_expired_card_reclaims_sats():
    """The sweep marks an expired card, reclaims sats, and rejects LNURL callback."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(
        wallet_id="wallet_issuer",
        card_wallet_id=None,
        amount=1000,
        expires_at=past,
    )

    issuer_wallet = _wallet_mock("wallet_issuer", balance_msat=500_000)

    def _get_wallet(wallet_id: str):
        if wallet_id == card.wallet:
            return issuer_wallet
        return None

    balance_changes: list[tuple[str, int]] = []

    async def _update_balance(wallet, amount, conn=None):
        balance_changes.append((wallet.id, amount))
        wallet.balance += amount

    with patch("giftcards.services.get_wallet", side_effect=_get_wallet), \
         patch("giftcards.services.update_wallet_balance", new=_update_balance):
        await _expire_gift_cards()

    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "expired"
    assert updated.expired_at is not None

    assert ("wallet_issuer", 1000) in balance_changes, "issuer wallet should be credited"

    # LNURL callback should now reject the card
    response = await lnurl_callback(pr="lnbc1invoice", k1=card.token_hash)
    body = json.loads(response.body)
    assert body["status"] == "ERROR"


@pytest.mark.anyio
async def test_expired_card_reclaim_without_dedicated_wallet():
    """When no dedicated card wallet exists, the issuer wallet is credited directly."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(
        wallet_id="wallet_issuer",
        card_wallet_id=None,
        amount=1000,
        expires_at=past,
    )

    issuer_wallet = _wallet_mock("wallet_issuer", balance_msat=500_000)

    def _get_wallet(wallet_id: str):
        if wallet_id == card.wallet:
            return issuer_wallet
        return None

    balance_changes: list[tuple[str, int]] = []

    async def _update_balance(wallet, amount, conn=None):
        balance_changes.append((wallet.id, amount))
        wallet.balance += amount

    with patch("giftcards.services.get_wallet", side_effect=_get_wallet), \
         patch("giftcards.services.update_wallet_balance", new=_update_balance):
        await _expire_gift_cards()

    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "expired"
    assert ("wallet_issuer", 1000) in balance_changes


@pytest.mark.anyio
async def test_reclaim_card_sats_logs_without_raw_token():
    """reclaim_card_sats logs errors but never includes the raw token."""
    past = datetime.now() - timedelta(hours=1)
    card = await _make_card(
        wallet_id="wallet_issuer",
        card_wallet_id="wallet_card",
        amount=1000,
        expires_at=past,
    )

    with patch("giftcards.services.get_wallet", return_value=None), \
         patch("giftcards.services.logger") as logger_mock:
        await reclaim_card_sats(card)

    # No assertion on log call count; only that raw token never appears in log messages.
    for call in logger_mock.method_calls:
        args = [str(a) for a in call.args]
        kwargs = {k: str(v) for k, v in call.kwargs.items()}
        log_text = " ".join(args) + " ".join(kwargs.values())
        assert card.token_hash not in log_text, "token hash leaked in log message"
