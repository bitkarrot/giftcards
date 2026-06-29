import pytest
import hashlib
from fastapi.testclient import TestClient
from lnbits.core.models import Wallet
from lnbits.core.services import create_payment_request
from lnbits.decorators import require_admin_key
from lnbits.wallets import get_funding_source

# These imports will fail until we implement the extension
from giftcards.models import GiftCard, CreateGiftCard, PublicGiftCard, CreateGiftCardResponse
from giftcards.services import create_gift_card
from giftcards.crud import get_card_by_token_hash, get_cards_by_wallet


@pytest.mark.asyncio
async def test_create_gift_card_returns_raw_token_and_urls():
    """Test 1: POST /giftcards/api/v1/cards creates a gift card and returns raw token and URLs."""
    # This test will fail because the giftcards extension doesn't exist yet
    client = TestClient(giftcards_app)
    
    # Create a test wallet with admin key
    wallet = await Wallet.create(
        user="test_user",
        wallet_name="Test Wallet",
        adminkey="test_admin_key",
        inkey="test_invoice_key"
    )
    
    # Fund the wallet with enough sats
    payment = await create_payment_request(
        wallet_id=wallet.id,
        invoice_data={"out": False, "amount": 10000, "memo": "Funding for gift card test"}
    )
    
    # Create gift card request
    create_data = {
        "amount": 1000,
        "recipient_name": "Bob",
        "sender_name": "Alice",
        "message": "Happy birthday!",
        "expires_at": None
    }
    
    response = client.post(
        "/giftcards/api/v1/cards",
        json=create_data,
        headers={"X-Api-Key": wallet.adminkey}
    )
    
    assert response.status_code == 200
    
    result = CreateGiftCardResponse(**response.json())
    
    # Verify raw token is 43 characters (secrets.token_urlsafe(32))
    assert len(result.raw_token) == 43
    
    # Verify redemption URL contains raw token
    assert f"/giftcards/redeem/{result.raw_token}" in result.redemption_url
    
    # Verify LNURL URL contains token hash (SHA-256 of raw token)
    token_hash = hashlib.sha256(result.raw_token.encode()).hexdigest()
    assert f"/giftcards/api/v1/lnurl/{token_hash}" in result.lnurl_url
    
    # Verify the card was created in database
    card = await get_card_by_token_hash(token_hash)
    assert card is not None
    assert card.amount == 1000
    assert card.recipient_name == "Bob"
    assert card.sender_name == "Alice"
    assert card.message == "Happy birthday!"


@pytest.mark.asyncio
async def test_list_cards_scoped_to_wallet():
    """Test 2: GET /giftcards/api/v1/cards returns cards for authenticated wallet only."""
    client = TestClient(giftcards_app)
    
    # Create two different wallets
    wallet1 = await Wallet.create(
        user="test_user1",
        wallet_name="Test Wallet 1",
        adminkey="test_admin_key1",
        inkey="test_invoice_key1"
    )
    
    wallet2 = await Wallet.create(
        user="test_user2",
        wallet_name="Test Wallet 2",
        adminkey="test_admin_key2",
        inkey="test_invoice_key2"
    )
    
    # Create cards for each wallet
    card1 = await create_gift_card(
        data=CreateGiftCard(amount=500, recipient_name="Alice"),
        issuer_wallet_id=wallet1.id,
        user_id=wallet1.user,
        base_url="http://test.com"
    )
    
    card2 = await create_gift_card(
        data=CreateGiftCard(amount=750, recipient_name="Bob"),
        issuer_wallet_id=wallet2.id,
        user_id=wallet2.user,
        base_url="http://test.com"
    )
    
    # List cards with wallet1's admin key
    response = client.get(
        "/giftcards/api/v1/cards",
        headers={"X-Api-Key": wallet1.adminkey}
    )
    
    assert response.status_code == 200
    cards = [GiftCard(**card) for card in response.json()]
    
    # Should only return wallet1's cards
    assert len(cards) == 1
    assert cards[0].id == card1.id
    assert cards[0].amount == 500
    
    # Verify sensitive fields are not exposed
    card_data = response.json()[0]
    assert "token_hash" not in card_data
    assert "card_wallet_id" not in card_data


@pytest.mark.asyncio
async def test_lnurl_params_returns_valid_withdraw_response():
    """Test 3: GET /giftcards/api/v1/lnurl/{token_hash} returns valid LNURL-withdraw JSON."""
    client = TestClient(giftcards_app)
    
    # Create a gift card
    wallet = await Wallet.create(
        user="test_user",
        wallet_name="Test Wallet",
        adminkey="test_admin_key",
        inkey="test_invoice_key"
    )
    
    card = await create_gift_card(
        data=CreateGiftCard(amount=1000, recipient_name="Bob"),
        issuer_wallet_id=wallet.id,
        user_id=wallet.user,
        base_url="http://test.com"
    )
    
    # Get LNURL params
    response = client.get(f"/giftcards/api/v1/lnurl/{card.token_hash}")
    
    assert response.status_code == 200
    
    lnurl_data = response.json()
    assert lnurl_data["tag"] == "withdrawRequest"
    assert lnurl_data["k1"] == card.token_hash
    assert lnurl_data["callback"].endswith(f"/giftcards/api/v1/lnurl/callback")
    assert lnurl_data["minWithdrawable"] == 1000000  # 1000 sats in millisats
    assert lnurl_data["maxWithdrawable"] == 1000000  # 1000 sats in millisats


@pytest.mark.asyncio
async def test_lnurl_callback_redeems_card():
    """Test 4: GET /giftcards/api/v1/lnurl/callback with valid BOLT11 redeems card."""
    client = TestClient(giftcards_app)
    
    # Create a gift card with dedicated wallet
    wallet = await Wallet.create(
        user="test_user",
        wallet_name="Test Wallet",
        adminkey="test_admin_key",
        inkey="test_invoice_key"
    )
    
    card = await create_gift_card(
        data=CreateGiftCard(amount=1000, recipient_name="Bob"),
        issuer_wallet_id=wallet.id,
        user_id=wallet.user,
        base_url="http://test.com"
    )
    
    # Create a BOLT11 invoice for redemption (from recipient wallet)
    recipient_payment = await create_payment_request(
        wallet_id="recipient_wallet_id",
        invoice_data={"out": False, "amount": 1000, "memo": "Redeem gift card"}
    )
    bolt11 = recipient_payment.payment_request
    
    # Call LNURL callback
    response = client.get(
        f"/giftcards/api/v1/lnurl/callback?pr={bolt11}&k1={card.token_hash}"
    )
    
    assert response.status_code == 200
    
    callback_data = response.json()
    assert callback_data["status"] == "OK"
    
    # Verify card is now redeemed
    updated_card = await get_card_by_token_hash(card.token_hash)
    assert updated_card.status == "redeemed"
    assert updated_card.redeemed_at is not None


@pytest.mark.asyncio
async def test_issuer_wallet_debited_after_creation():
    """Test 5: Issuer wallet balance decreases by card amount after creation."""
    # Get initial wallet balance
    wallet = await Wallet.create(
        user="test_user",
        wallet_name="Test Wallet",
        adminkey="test_admin_key",
        inkey="test_invoice_key"
    )
    
    # Fund wallet with 5000 sats
    funding_payment = await create_payment_request(
        wallet_id=wallet.id,
        invoice_data={"out": False, "amount": 5000, "memo": "Initial funding"}
    )
    
    initial_balance = await get_wallet_balance(wallet.id)
    
    # Create gift card for 1000 sats
    client = TestClient(giftcards_app)
    create_data = {"amount": 1000}
    
    response = client.post(
        "/giftcards/api/v1/cards",
        json=create_data,
        headers={"X-Api-Key": wallet.adminkey}
    )
    
    assert response.status_code == 200
    
    # Check wallet balance decreased by 1000 sats
    final_balance = await get_wallet_balance(wallet.id)
    assert final_balance == initial_balance - 1000


@pytest.mark.asyncio
async def test_public_card_endpoint_hides_sensitive_data():
    """Test 6: GET /giftcards/api/v1/cards/public/{token_hash} returns PublicGiftCard."""
    client = TestClient(giftcards_app)
    
    # Create a gift card
    wallet = await Wallet.create(
        user="test_user",
        wallet_name="Test Wallet",
        adminkey="test_admin_key",
        inkey="test_invoice_key"
    )
    
    card = await create_gift_card(
        data=CreateGiftCard(
            amount=1000,
            recipient_name="Bob",
            sender_name="Alice",
            message="Happy birthday!"
        ),
        issuer_wallet_id=wallet.id,
        user_id=wallet.user,
        base_url="http://test.com"
    )
    
    # Get public card details
    response = client.get(f"/giftcards/api/v1/cards/public/{card.token_hash}")
    
    assert response.status_code == 200
    
    public_card = PublicGiftCard(**response.json())
    
    # Verify public data is present
    assert public_card.status == "active"
    assert public_card.amount == 1000
    assert public_card.sender_name == "Alice"
    assert public_card.message == "Happy birthday!"
    
    # Verify sensitive data is NOT present
    card_data = response.json()
    assert "wallet" not in card_data
    assert "card_wallet_id" not in card_data
    assert "token_hash" not in card_data


# Helper functions (these will need to be implemented)
async def get_wallet_balance(wallet_id: str) -> int:
    """Get wallet balance in sats."""
    wallet = await Wallet.get(wallet_id)
    return wallet.balance_msat // 1000


# Mock app for testing (will be replaced with actual app)
giftcards_app = None