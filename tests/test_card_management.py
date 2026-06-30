"""Tests for card management — update (PUT) and delete (DELETE) with sats reclaim.

Phase 3 — Plan 03-02 (TDD RED phase).

These tests cover:
- UpdateCardRequest with recipient_name validates; amount field does not exist
- reclaim_sats_and_delete on an active card calls reclaim_card_sats then delete_card
- reclaim_sats_and_delete on an expired card skips reclaim and deletes the record
- DELETE endpoint on a redeemed card returns 409 (tested at service/endpoint layer)
- api_update_card updates card fields and returns {status: updated}
- api_delete_card on active card reclaims sats and deletes record
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from giftcards.crud import create_card, db, get_card
from giftcards.migrations import m001_initial, m002_add_raw_token, m003_branded_delivery
from giftcards.models import GiftCard
from giftcards.services import generate_token

# Import guards — RED phase: these imports will fail until Task 2 implements them
try:
    from giftcards.models import UpdateCardRequest
    from giftcards.services import reclaim_sats_and_delete
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Test fixtures (mirror test_bulk_creation.py patterns)
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
# UpdateCardRequest model tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_update_card_request_valid():
    """UpdateCardRequest with recipient_name='New Name' validates successfully."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    req = UpdateCardRequest(recipient_name="New Name")
    assert req.recipient_name == "New Name"


@pytest.mark.anyio
async def test_update_card_request_no_amount_field():
    """UpdateCardRequest does NOT have an 'amount' field (D-15 — amount not editable)."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    req = UpdateCardRequest(recipient_name="New Name", sender_name="Alice")
    # amount should not be a field on the model
    assert not hasattr(req, "amount")
    # Attempting to set amount should raise (or be ignored by Pydantic)
    field_names = set(req.__fields__.keys())
    assert "amount" not in field_names


# ---------------------------------------------------------------------------
# reclaim_sats_and_delete service tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_reclaim_sats_and_delete_active_card():
    """reclaim_sats_and_delete on an active card calls reclaim_card_sats
    then delete_card (card no longer in DB)."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    card = await _make_card(wallet_id="wallet_issuer", amount=1000, status="active")

    balance_changes = []

    async def _update_balance(wallet, amount, conn=None):
        balance_changes.append((wallet.id, amount))

    with patch("giftcards.services.get_wallet") as mock_get_wallet, \
         patch("giftcards.services.update_wallet_balance", new=_update_balance):
        mock_wallet = MagicMock()
        mock_wallet.id = "wallet_issuer"
        mock_get_wallet.return_value = mock_wallet

        await reclaim_sats_and_delete(card)

    # Sats should be reclaimed (credited back)
    assert ("wallet_issuer", 1000) in balance_changes
    # Card should be deleted from DB
    deleted = await get_card(card.id)
    assert deleted is None


@pytest.mark.anyio
async def test_reclaim_sats_and_delete_expired_card():
    """reclaim_sats_and_delete on an expired card skips reclaim (sats already
    reclaimed) and deletes the record."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    card = await _make_card(wallet_id="wallet_issuer", amount=1000, status="expired")

    balance_changes = []

    async def _update_balance(wallet, amount, conn=None):
        balance_changes.append((wallet.id, amount))

    with patch("giftcards.services.get_wallet") as mock_get_wallet, \
         patch("giftcards.services.update_wallet_balance", new=_update_balance):
        mock_wallet = MagicMock()
        mock_wallet.id = "wallet_issuer"
        mock_get_wallet.return_value = mock_wallet

        await reclaim_sats_and_delete(card)

    # Sats should NOT be reclaimed for expired cards (already reclaimed by expiry task)
    assert len(balance_changes) == 0
    # Card should still be deleted from DB
    deleted = await get_card(card.id)
    assert deleted is None


# ---------------------------------------------------------------------------
# DELETE endpoint — redeemed card returns 409
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_delete_redeemed_card_returns_409():
    """DELETE endpoint on a redeemed card returns 409 (tested at endpoint layer)."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    from fastapi import HTTPException
    from giftcards.views_api import api_delete_card

    card = await _make_card(wallet_id="wallet_a", status="redeemed")

    with pytest.raises(HTTPException) as exc_info:
        await api_delete_card(card_id=card.id, wallet=_wallet_mock("wallet_a"))

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# PUT endpoint — updates card fields
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_api_update_card_updates_fields():
    """PUT /cards/{id} updates recipient_name and returns {status: updated}."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    from giftcards.views_api import api_update_card

    card = await _make_card(wallet_id="wallet_a", recipient_name="Old Name")

    req = UpdateCardRequest(recipient_name="New Name")
    result = await api_update_card(
        card_id=card.id,
        data=req,
        wallet=_wallet_mock("wallet_a"),
    )

    assert result["status"] == "updated"
    updated = await get_card(card.id)
    assert updated.recipient_name == "New Name"


@pytest.mark.anyio
async def test_api_update_card_cross_wallet_forbidden():
    """PUT /cards/{id} on another wallet's card returns 403."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    from fastapi import HTTPException
    from giftcards.views_api import api_update_card

    card = await _make_card(wallet_id="wallet_a")

    req = UpdateCardRequest(recipient_name="New Name")
    with pytest.raises(HTTPException) as exc_info:
        await api_update_card(
            card_id=card.id,
            data=req,
            wallet=_wallet_mock("wallet_b"),
        )

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# DELETE endpoint — active card reclaims and deletes
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_api_delete_card_active_reclaims_and_deletes():
    """DELETE /cards/{id} on an active card reclaims sats and deletes the record."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")

    from giftcards.views_api import api_delete_card

    card = await _make_card(wallet_id="wallet_a", amount=500, status="active")

    balance_changes = []

    async def _update_balance(wallet, amount, conn=None):
        balance_changes.append((wallet.id, amount))

    with patch("giftcards.services.get_wallet") as mock_get_wallet, \
         patch("giftcards.services.update_wallet_balance", new=_update_balance):
        mock_wallet = MagicMock()
        mock_wallet.id = "wallet_a"
        mock_get_wallet.return_value = mock_wallet

        result = await api_delete_card(
            card_id=card.id,
            wallet=_wallet_mock("wallet_a"),
        )

    assert result["status"] == "deleted"
    assert result["reclaimed_sats"] == 500
    assert ("wallet_a", 500) in balance_changes
    deleted = await get_card(card.id)
    assert deleted is None
