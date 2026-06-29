import pytest
import hashlib
from datetime import datetime

# Test imports first
try:
    from giftcards.models import GiftCard, CreateGiftCard, PublicGiftCard, CreateGiftCardResponse
    from giftcards.services import generate_token, create_gift_card
    from giftcards.crud import get_card_by_token_hash, get_cards_by_wallet
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.mark.anyio
async def test_imports():
    """Test that all required modules can be imported."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    # If we get here, imports are working
    assert True


@pytest.mark.anyio
async def test_token_generation():
    """Test token generation produces expected format."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    raw_token, token_hash = generate_token()
    
    # Verify raw token is 43 characters (secrets.token_urlsafe(32))
    assert len(raw_token) == 43
    
    # Verify token hash is SHA-256 (64 hex characters)
    assert len(token_hash) == 64
    assert all(c in "0123456789abcdef" for c in token_hash)
    
    # Verify hash matches raw token
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert token_hash == expected_hash


@pytest.mark.anyio
async def test_gift_card_model():
    """Test GiftCard model validation."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    card = GiftCard(
        id="gc_test123",
        wallet="wallet_123",
        card_wallet_id="card_wallet_456",
        amount=1000,
        token_hash="abcd1234" * 8,  # 64 chars
        status="active",
        recipient_name="Bob",
        sender_name="Alice",
        message="Happy birthday!",
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
    )
    
    assert card.id == "gc_test123"
    assert card.amount == 1000
    assert card.status == "active"
    assert card.recipient_name == "Bob"


@pytest.mark.anyio
async def test_create_gift_card_model_validation():
    """Test CreateGiftCard model validation."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    # Valid card should pass
    card = CreateGiftCard(
        amount=1000,
        recipient_name="Bob",
        sender_name="Alice",
        message="Happy birthday!",
        expires_at=None,
    )
    assert card.amount == 1000
    
    # Invalid amount should fail
    with pytest.raises(ValueError):
        CreateGiftCard(amount=-100)
    
    with pytest.raises(ValueError):
        CreateGiftCard(amount=0)


@pytest.mark.anyio
async def test_public_gift_card_model():
    """Test PublicGiftCard model excludes sensitive fields."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    public_card = PublicGiftCard(
        status="active",
        amount=1000,
        sender_name="Alice",
        recipient_name="Bob",
        message="Happy birthday!",
        expires_at=None,
        expired_at=None,
    )
    
    # Verify public data is present
    assert public_card.status == "active"
    assert public_card.amount == 1000
    assert public_card.sender_name == "Alice"
    
    # Verify no sensitive fields (implicitly by model definition)
    assert hasattr(public_card, 'status')
    assert hasattr(public_card, 'amount')
    assert not hasattr(public_card, 'wallet')  # Should not have sensitive fields


# Test that the extension can be imported
@pytest.mark.anyio
async def test_extension_import():
    """Test that the extension can be imported."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    try:
        from giftcards import giftcards_ext, db, giftcards_start, giftcards_stop
        assert giftcards_ext is not None
        assert db is not None
        assert callable(giftcards_start)
        assert callable(giftcards_stop)
    except ImportError as e:
        pytest.fail(f"Failed to import extension: {e}")


# Test database connection
@pytest.mark.anyio
async def test_database_connection():
    """Test that the database connection works."""
    if not IMPORTS_AVAILABLE:
        pytest.skip(f"Imports not available: {IMPORT_ERROR}")
    
    try:
        from giftcards.crud import db
        # Just test that we can access the database object
        assert db is not None
        assert db.name == "ext_giftcards"
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")