"""Tests for the filtered dashboard query (get_cards_by_wallet_filtered).

Phase 3 — Plan 03-03 (TDD RED phase).

These tests cover:
- get_cards_by_wallet_filtered with status filter returns only matching cards
- get_cards_by_wallet_filtered with search filter (case-insensitive on
  recipient_name, sender_name, id)
- get_cards_by_wallet_filtered with date_from / date_to filters
- get_cards_by_wallet_filtered with no filters returns all cards for the wallet
- get_cards_by_wallet_filtered with combined filters (status + search + date)
- get_cards_by_wallet_filtered enforces cross-wallet isolation (T-03-15)

Per RESEARCH.md Pattern 4 (Server-Side Filtered Query) and Pitfall 3
(cross-DB case-insensitivity via LOWER(col) LIKE LOWER(:search)).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from giftcards.crud import create_card, db, get_card
from giftcards.migrations import (
    m001_initial,
    m002_add_raw_token,
    m003_branded_delivery,
    m004_dashboard_indexes,
)
from giftcards.models import GiftCard
from giftcards.services import generate_token


# ---------------------------------------------------------------------------
# Test fixtures (mirror test_bulk_creation.py patterns)
# ---------------------------------------------------------------------------

async def _reset_table():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await m001_initial(db)
    await m002_add_raw_token(db)
    await m003_branded_delivery(db)
    await m004_dashboard_indexes(db)


async def _make_card(
    wallet_id: str = "wallet_test",
    amount: int = 1000,
    status: str = "active",
    recipient_name: str = "Bob",
    sender_name: str = "Alice",
    message: str = "Hello",
    created_at: datetime = None,
    recipient_email: str = None,
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
        created_at=created_at or datetime.now(timezone.utc),
        redeemed_at=None,
        expired_at=None,
        recipient_email=recipient_email,
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
# Filtered query tests (TDD RED — get_cards_by_wallet_filtered does not exist yet)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_filtered_status_active_returns_only_active():
    """get_cards_by_wallet_filtered(status='active') returns only active cards."""
    from giftcards.crud import get_cards_by_wallet_filtered

    await _make_card(status="active", recipient_name="Active One")
    await _make_card(status="redeemed", recipient_name="Redeemed One")
    await _make_card(status="expired", recipient_name="Expired One")

    cards = await get_cards_by_wallet_filtered("wallet_test", status="active")
    assert len(cards) == 1
    assert cards[0].status == "active"
    assert cards[0].recipient_name == "Active One"


@pytest.mark.anyio
async def test_filtered_status_redeemed_returns_only_redeemed():
    """get_cards_by_wallet_filtered(status='redeemed') returns only redeemed cards."""
    from giftcards.crud import get_cards_by_wallet_filtered

    await _make_card(status="active", recipient_name="Active One")
    await _make_card(status="redeemed", recipient_name="Redeemed One")

    cards = await get_cards_by_wallet_filtered("wallet_test", status="redeemed")
    assert len(cards) == 1
    assert cards[0].status == "redeemed"
    assert cards[0].recipient_name == "Redeemed One"


@pytest.mark.anyio
async def test_filtered_search_case_insensitive_recipient():
    """get_cards_by_wallet_filtered(search='alice') matches recipient_name case-insensitively."""
    from giftcards.crud import get_cards_by_wallet_filtered

    await _make_card(recipient_name="Alice Smith", sender_name="Bob")
    await _make_card(recipient_name="Charlie", sender_name="alice Jones")
    await _make_card(recipient_name="Dave", sender_name="Eve")

    cards = await get_cards_by_wallet_filtered("wallet_test", search="alice")
    # Should match both "Alice Smith" (recipient) and "alice Jones" (sender)
    assert len(cards) == 2
    names = {c.recipient_name for c in cards}
    assert "Alice Smith" in names
    assert "Charlie" in names


@pytest.mark.anyio
async def test_filtered_search_matches_card_id():
    """get_cards_by_wallet_filtered(search=<partial id>) matches the card id."""
    from giftcards.crud import get_cards_by_wallet_filtered

    card = await _make_card(recipient_name="Zoe", sender_name="Yan")
    await _make_card(recipient_name="Other", sender_name="Person")

    # Use a substring of the card id
    search_term = card.id[3:11]
    cards = await get_cards_by_wallet_filtered("wallet_test", search=search_term)
    assert len(cards) == 1
    assert cards[0].id == card.id


@pytest.mark.anyio
async def test_filtered_date_from_returns_cards_after_date():
    """get_cards_by_wallet_filtered(date_from=ts) returns only cards created after date_from."""
    from giftcards.crud import get_cards_by_wallet_filtered

    old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    new_time = datetime(2026, 6, 1, tzinfo=timezone.utc)
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)

    await _make_card(recipient_name="Old", created_at=old_time)
    await _make_card(recipient_name="New", created_at=new_time)

    cards = await get_cards_by_wallet_filtered(
        "wallet_test", date_from=cutoff.timestamp()
    )
    assert len(cards) == 1
    assert cards[0].recipient_name == "New"


@pytest.mark.anyio
async def test_filtered_date_to_returns_cards_before_date():
    """get_cards_by_wallet_filtered(date_to=ts) returns only cards created before date_to."""
    from giftcards.crud import get_cards_by_wallet_filtered

    old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    new_time = datetime(2026, 6, 1, tzinfo=timezone.utc)
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)

    await _make_card(recipient_name="Old", created_at=old_time)
    await _make_card(recipient_name="New", created_at=new_time)

    cards = await get_cards_by_wallet_filtered(
        "wallet_test", date_to=cutoff.timestamp()
    )
    assert len(cards) == 1
    assert cards[0].recipient_name == "Old"


@pytest.mark.anyio
async def test_filtered_no_filters_returns_all_cards():
    """get_cards_by_wallet_filtered with no filters returns all cards for the wallet."""
    from giftcards.crud import get_cards_by_wallet_filtered

    await _make_card(status="active", recipient_name="A")
    await _make_card(status="redeemed", recipient_name="B")
    await _make_card(status="expired", recipient_name="C")

    cards = await get_cards_by_wallet_filtered("wallet_test")
    assert len(cards) == 3


@pytest.mark.anyio
async def test_filtered_combined_status_search_date():
    """get_cards_by_wallet_filtered with status + search + date range combines filters with AND."""
    from giftcards.crud import get_cards_by_wallet_filtered

    t1 = datetime(2025, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 15, tzinfo=timezone.utc)
    t3 = datetime(2026, 3, 10, tzinfo=timezone.utc)

    # Matches all three filters
    await _make_card(
        status="active", recipient_name="Alice", sender_name="Bob", created_at=t2
    )
    # Wrong status
    await _make_card(
        status="redeemed", recipient_name="Alice", sender_name="Bob", created_at=t2
    )
    # Wrong search
    await _make_card(
        status="active", recipient_name="Zoe", sender_name="Yan", created_at=t2
    )
    # Outside date range (too old)
    await _make_card(
        status="active", recipient_name="Alice", sender_name="Bob", created_at=t1
    )

    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    date_to = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()

    cards = await get_cards_by_wallet_filtered(
        "wallet_test",
        status="active",
        search="alice",
        date_from=date_from,
        date_to=date_to,
    )
    assert len(cards) == 1
    assert cards[0].recipient_name == "Alice"
    assert cards[0].status == "active"


@pytest.mark.anyio
async def test_filtered_cross_wallet_isolation():
    """get_cards_by_wallet_filtered only returns cards for the specified wallet (T-03-15)."""
    from giftcards.crud import get_cards_by_wallet_filtered

    await _make_card(wallet_id="wallet_a", recipient_name="Card A1")
    await _make_card(wallet_id="wallet_a", recipient_name="Card A2")
    await _make_card(wallet_id="wallet_b", recipient_name="Card B1")

    cards_a = await get_cards_by_wallet_filtered("wallet_a")
    cards_b = await get_cards_by_wallet_filtered("wallet_b")

    assert len(cards_a) == 2
    assert all(c.recipient_name.startswith("Card A") for c in cards_a)
    assert len(cards_b) == 1
    assert cards_b[0].recipient_name == "Card B1"


@pytest.mark.anyio
async def test_filtered_results_ordered_by_created_at_desc():
    """get_cards_by_wallet_filtered returns cards ordered by created_at DESC."""
    from giftcards.crud import get_cards_by_wallet_filtered

    t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t3 = datetime(2026, 6, 1, tzinfo=timezone.utc)

    await _make_card(recipient_name="Oldest", created_at=t1)
    await _make_card(recipient_name="Newest", created_at=t3)
    await _make_card(recipient_name="Middle", created_at=t2)

    cards = await get_cards_by_wallet_filtered("wallet_test")
    assert len(cards) == 3
    # Newest first
    assert cards[0].recipient_name == "Newest"
    assert cards[1].recipient_name == "Middle"
    assert cards[2].recipient_name == "Oldest"
