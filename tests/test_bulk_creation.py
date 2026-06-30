"""Tests for bulk gift card creation, invoice-key reads, and include_link flag.

Phase 3 — Plan 03-01 (TDD RED phase).

These tests cover:
- BulkCreateRequest model validation (count gt=0 le=500, amount gt=0)
- bulk_create_with_funding service (loops create_gift_card)
- CardDetailResponse with optional redemption_url (include_link flag)
- GET /cards with invoice key returns GiftCardSummary list
- GET /cards/{id} ownership check (403 for other wallet's card)
- GET /cards/{id} include_link=true populates redemption_url
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from giftcards.crud import create_card, db, get_card
from giftcards.migrations import m001_initial, m002_add_raw_token, m003_branded_delivery
from giftcards.models import GiftCard
from giftcards.services import generate_token


# ---------------------------------------------------------------------------
# Test fixtures (mirror test_security.py patterns)
# ---------------------------------------------------------------------------

async def _reset_table():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await m001_initial(db)
    await m002_add_raw_token(db)
    await m003_branded_delivery(db)


async def _make_card(
    wallet_id: str = "wallet_test",
    amount: int = 1000,
    status: str = "active",
    recipient_name: str = "Bob",
    sender_name: str = "Alice",
    message: str = "Hello",
) -> GiftCard:
    raw_token, token_hash = generate_token()
    card = GiftCard(
        id=f"gc_{token_hash[:16]}",
        wallet=wallet_id,
        card_wallet_id=None,
        amount=amount,
        token_hash=token_hash,
        raw_token=raw_token,
        redemption_url=f"https://example.com/giftcards/redeem/{raw_token}",
        status=status,
        recipient_name=recipient_name,
        sender_name=sender_name,
        message=message,
        expires_at=None,
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


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_bulk_create_request_valid():
    """BulkCreateRequest(count=3, amount=1000) validates successfully."""
    from giftcards.models import BulkCreateRequest

    req = BulkCreateRequest(count=3, amount=1000)
    assert req.count == 3
    assert req.amount == 1000


@pytest.mark.anyio
async def test_bulk_create_request_count_zero_rejected():
    """BulkCreateRequest with count=0 raises validation error."""
    from giftcards.models import BulkCreateRequest

    with pytest.raises(ValueError):
        BulkCreateRequest(count=0, amount=1000)


@pytest.mark.anyio
async def test_bulk_create_request_count_over_500_rejected():
    """BulkCreateRequest with count=501 raises validation error (max 500)."""
    from giftcards.models import BulkCreateRequest

    with pytest.raises(ValueError):
        BulkCreateRequest(count=501, amount=1000)


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_bulk_create_with_funding_creates_n_cards():
    """bulk_create_with_funding with 3 rows calls create_gift_card 3 times
    and returns 3 CreateGiftCardResponse objects with unique token_hashes."""
    from giftcards.models import CreateGiftCard
    from giftcards.services import bulk_create_with_funding

    rows = [
        CreateGiftCard(amount=1000, recipient_name=f"Recipient {i}")
        for i in range(3)
    ]

    with patch("giftcards.services.create_gift_card") as mock_create:
        # Each call returns a mock response with a unique token_hash
        async def _fake_create(data, issuer_wallet_id, user_id, base_url):
            _, token_hash = generate_token()
            resp = MagicMock()
            resp.card = MagicMock()
            resp.card.id = f"gc_{token_hash[:16]}"
            resp.raw_token = f"token_{token_hash[:8]}"
            resp.redemption_url = f"{base_url}redeem/{resp.raw_token}"
            resp.lnurl_url = f"{base_url}lnurl/{token_hash}"
            return resp

        mock_create.side_effect = _fake_create

        responses = await bulk_create_with_funding(
            rows=rows,
            issuer_wallet_id="wallet_test",
            user_id="user_test",
            base_url="https://example.com/",
        )

    assert len(responses) == 3
    assert mock_create.call_count == 3
    # Each response should have a unique card id
    card_ids = [r.card.id for r in responses]
    assert len(set(card_ids)) == 3


# ---------------------------------------------------------------------------
# API endpoint tests (service/CRUD layer — matching test_security.py style)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_api_get_cards_with_invoice_key():
    """GET /giftcards/api/v1/cards with invoice key returns list of
    GiftCardSummary for that wallet."""
    from giftcards.views_api import api_get_cards

    await _make_card(wallet_id="wallet_a")
    await _make_card(wallet_id="wallet_a")
    await _make_card(wallet_id="wallet_b")

    cards = await api_get_cards(wallet=_wallet_mock("wallet_a"))

    assert len(cards) == 2
    for card in cards:
        assert card.amount == 1000


@pytest.mark.anyio
async def test_api_get_card_detail_without_include_link():
    """GET /giftcards/api/v1/cards/{card_id} without ?include_link=true
    returns CardDetailResponse with redemption_url=None."""
    from giftcards.views_api import api_get_card_detail

    card = await _make_card(wallet_id="wallet_a")

    response = await api_get_card_detail(
        card_id=card.id,
        include_link=False,
        wallet=_wallet_mock("wallet_a"),
    )

    assert response.card_id == card.id
    assert response.amount == card.amount
    assert response.redemption_url is None


@pytest.mark.anyio
async def test_api_get_card_detail_with_include_link():
    """GET /giftcards/api/v1/cards/{card_id}?include_link=true returns
    CardDetailResponse with redemption_url populated."""
    from giftcards.views_api import api_get_card_detail

    card = await _make_card(wallet_id="wallet_a")

    response = await api_get_card_detail(
        card_id=card.id,
        include_link=True,
        wallet=_wallet_mock("wallet_a"),
    )

    assert response.card_id == card.id
    assert response.redemption_url is not None
    assert response.redemption_url == card.redemption_url


@pytest.mark.anyio
async def test_api_get_card_detail_cross_wallet_forbidden():
    """GET /giftcards/api/v1/cards/{card_id} for a card belonging to a
    different wallet returns 403."""
    from fastapi import HTTPException
    from giftcards.views_api import api_get_card_detail

    card = await _make_card(wallet_id="wallet_a")

    with pytest.raises(HTTPException) as exc_info:
        await api_get_card_detail(
            card_id=card.id,
            include_link=False,
            wallet=_wallet_mock("wallet_b"),
        )

    assert exc_info.value.status_code == 403
