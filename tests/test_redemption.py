import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from lnbits.core.models.payments import Payment, PaymentState
from lnbits.exceptions import PaymentError

from giftcards.crud import (
    create_card,
    db,
    get_card_by_token_hash,
    mark_redeemed,
    mark_redeeming,
    reset_to_active,
)
from giftcards.migrations import m001_initial
from giftcards.models import GiftCard
from giftcards.services import generate_token, pay_and_complete
from giftcards.views_api import lnurl_callback


async def _reset_table():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await m001_initial(db)


async def _make_card(status="active") -> GiftCard:
    raw_token, token_hash = generate_token()
    card = GiftCard(
        id=f"gc_{token_hash[:16]}",
        wallet="wallet_test",
        card_wallet_id="wallet_card",
        amount=1000,
        token_hash=token_hash,
        status=status,
        recipient_name="Bob",
        sender_name="Alice",
        message="Hello",
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
    )
    await create_card(card)
    return card


def _payment(card, bolt11, status):
    return Payment(
        checking_id="chk_test",
        payment_hash="ph_test",
        wallet_id=card.card_wallet_id or card.wallet,
        amount=-card.amount * 1000,
        fee=0,
        bolt11=bolt11,
        status=status,
        memo="Redeem gift card",
    )


@pytest.fixture(autouse=True)
async def clean_table():
    await _reset_table()
    yield
    await _reset_table()


@pytest.fixture
def wallet_mock():
    wallet = MagicMock()
    wallet.id = "wallet_card"
    wallet.can_send_payments = True
    return wallet


@pytest.mark.anyio
async def test_concurrent_redemption_no_double_spend(wallet_mock):
    """Two concurrent callbacks for the same active card result in one success and one error."""
    card = await _make_card("active")
    pr1 = "lnbc1invoice1"
    pr2 = "lnbc1invoice2"

    def _side_effect(*args, **kwargs):
        bolt11 = kwargs.get("payment_request") or args[1]
        return _payment(card, bolt11, PaymentState.SUCCESS)

    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, side_effect=_side_effect) as pay_mock:
        results = await asyncio.gather(
            lnurl_callback(pr=pr1, k1=card.token_hash),
            lnurl_callback(pr=pr2, k1=card.token_hash),
        )

    bodies = [json.loads(r.body) for r in results]
    success_count = sum(1 for b in bodies if b.get("status") == "OK")
    error_count = sum(1 for b in bodies if b.get("status") == "ERROR")
    assert success_count == 1, f"expected exactly one success, got {bodies}"
    assert error_count == 1, f"expected exactly one error, got {bodies}"

    # The winning payment should have been attempted exactly once
    assert pay_mock.await_count == 1

    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "redeemed"


@pytest.mark.anyio
async def test_mismatched_k1_returns_error_and_leaves_card_active(wallet_mock):
    """A callback with a k1 that does not match any card returns an error and touches nothing."""
    card = await _make_card("active")
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock) as pay_mock:
        response = await lnurl_callback(pr="lnbc1invoice", k1="not_a_real_hash")

    pay_mock.assert_not_awaited()
    body = json.loads(response.body)
    assert body["status"] == "ERROR"
    assert response.status_code == 400
    assert "not_a_real_hash" not in body.get("reason", "")
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "active"


@pytest.mark.anyio
async def test_missing_pr_returns_error_and_leaves_card_active(wallet_mock):
    """A callback with a missing or empty pr returns an error before locking the card."""
    card = await _make_card("active")
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock) as pay_mock:
        response = await lnurl_callback(pr="", k1=card.token_hash)

    pay_mock.assert_not_awaited()
    body = json.loads(response.body)
    assert body["status"] == "ERROR"
    assert response.status_code == 400
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "active"


@pytest.mark.anyio
async def test_payment_error_resets_card_to_active(wallet_mock):
    """If pay_invoice raises PaymentError, the card returns to active and the callback errors."""
    card = await _make_card("active")
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, side_effect=PaymentError("payment failed")):
        response = await lnurl_callback(pr="lnbc1invoice", k1=card.token_hash)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["status"] == "ERROR"
    assert "payment failed" not in body.get("reason", "")
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "active"


@pytest.mark.anyio
async def test_pending_payment_resets_card_to_active(wallet_mock):
    """If pay_invoice returns a pending payment, the card returns to active and the callback errors."""
    card = await _make_card("active")
    pending = _payment(card, "lnbc1invoice", PaymentState.PENDING)
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, return_value=pending):
        response = await lnurl_callback(pr="lnbc1invoice", k1=card.token_hash)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["status"] == "ERROR"
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "active"


@pytest.mark.anyio
async def test_pay_and_complete_returns_payment_on_success(wallet_mock):
    """pay_and_complete returns the Payment object on success."""
    card = await _make_card("active")
    success = _payment(card, "lnbc1invoice", PaymentState.SUCCESS)
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, return_value=success):
        result = await pay_and_complete(card, "lnbc1invoice")

    assert result == success


@pytest.mark.anyio
async def test_pay_and_complete_raises_on_payment_error(wallet_mock):
    """pay_and_complete re-raises PaymentError instead of swallowing it."""
    card = await _make_card("active")
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, side_effect=PaymentError("failed")):
        with pytest.raises(PaymentError):
            await pay_and_complete(card, "lnbc1invoice")


@pytest.mark.anyio
async def test_pay_and_complete_raises_on_pending_payment(wallet_mock):
    """pay_and_complete raises when the returned payment is not in success state."""
    card = await _make_card("active")
    pending = _payment(card, "lnbc1invoice", PaymentState.PENDING)
    with patch("giftcards.services.get_wallet", return_value=wallet_mock), \
         patch("giftcards.services.pay_invoice", new_callable=AsyncMock, return_value=pending):
        with pytest.raises(Exception):
            await pay_and_complete(card, "lnbc1invoice")


@pytest.mark.anyio
async def test_mark_redeeming_returns_none_for_non_active_card():
    """The atomic guard only wins when the card is active."""
    card = await _make_card("redeemed")
    assert await mark_redeeming(card.token_hash) is None


@pytest.mark.anyio
async def test_mark_redeemed_sets_redeemed_at():
    """mark_redeemed transitions the card to redeemed and sets a timestamp."""
    card = await _make_card("active")
    await mark_redeemed(card.id)
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "redeemed"
    assert updated.redeemed_at is not None


@pytest.mark.anyio
async def test_reset_to_active_recover_redeeming_card():
    """reset_to_active moves a stuck card back to active."""
    card = await _make_card("redeeming")
    await reset_to_active(card.id)
    updated = await get_card_by_token_hash(card.token_hash)
    assert updated.status == "active"
