import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from giftcards.crud import create_card, db, get_cards_by_wallet
from giftcards.migrations import m001_initial
from giftcards.models import GiftCard
from giftcards.services import generate_token
from giftcards.views_api import api_get_cards, api_get_public_card


async def _reset_table():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await m001_initial(db)


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


def _wallet_mock(wallet_id: str):
    wallet_type_info = MagicMock()
    wallet_type_info.wallet.id = wallet_id
    wallet_type_info.wallet.user = "user_test"
    return wallet_type_info


@pytest.mark.anyio
async def test_token_hash_not_in_list_response():
    """GET /api/v1/cards response never contains token_hash or card_wallet_id."""
    await _make_card(wallet_id="wallet_a")

    cards = await api_get_cards(wallet=_wallet_mock("wallet_a"))
    response_text = " ".join(c.json() for c in cards)

    assert "token_hash" not in response_text
    assert "card_wallet_id" not in response_text
    assert "wallet" not in response_text


@pytest.mark.anyio
async def test_raw_token_not_stored_in_database():
    """The database stores only the SHA-256 token hash; no raw token column exists."""
    card = await _make_card(wallet_id="wallet_a")

    rows = await db.fetchall(
        "PRAGMA table_info(cards)",
        {},
    )
    columns = {r["name"] for r in rows}

    assert "raw_token" not in columns, "raw token column must not exist"
    assert "token_hash" in columns, "token hash column must exist"

    # Verify the stored hash is a 64-character hex string (SHA-256).
    assert len(card.token_hash) == 64
    assert all(c in "0123456789abcdef" for c in card.token_hash)


@pytest.mark.anyio
async def test_cross_wallet_list_access_denied():
    """A wallet cannot list cards created by a different wallet."""
    card_a = await _make_card(wallet_id="wallet_a")
    await _make_card(wallet_id="wallet_b")

    cards = await get_cards_by_wallet("wallet_a")
    assert len(cards) == 1
    assert cards[0].id == card_a.id


@pytest.mark.anyio
async def test_cross_wallet_api_list_access_denied():
    """The issuer API endpoint only returns cards scoped to the authenticated wallet."""
    card_a = await _make_card(wallet_id="wallet_a")
    await _make_card(wallet_id="wallet_b")

    cards = await api_get_cards(wallet=_wallet_mock("wallet_a"))
    assert len(cards) == 1
    assert cards[0].id == card_a.id


@pytest.mark.anyio
async def test_public_endpoint_safe_fields():
    """The public card endpoint returns only safe fields."""
    card = await _make_card(wallet_id="wallet_a", card_wallet_id="wallet_card")

    public = await api_get_public_card(card.token_hash)
    public_dict = public.dict()

    assert "wallet" not in public_dict
    assert "card_wallet_id" not in public_dict
    assert "token_hash" not in public_dict
    assert "id" not in public_dict or public_dict.get("id") is None

    assert public_dict["status"] == card.status
    assert public_dict["amount"] == card.amount
