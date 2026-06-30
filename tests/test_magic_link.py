"""Tests for Phase 2 magic link flow and email delivery (plan 02-03).

Task 1 tests: magic link CRUD, claim endpoints, rate limiting, claim page.
Task 2 tests: Jinja2 email templates, SMTP send, deliver endpoint, email dialog.
"""
import asyncio
import inspect
import time
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from giftcards.crud import (
    db,
    create_card,
)
from giftcards.migrations import m001_initial, m002_add_raw_token, m003_branded_delivery
from giftcards.models import GiftCard, ClaimRequest, DeliverRequest
from giftcards.services import generate_token


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

async def _reset_tables():
    await db.execute("DROP TABLE IF EXISTS giftcards.cards")
    await db.execute("DROP TABLE IF EXISTS giftcards.magic_links")
    await m001_initial(db)
    await m002_add_raw_token(db)
    await m003_branded_delivery(db)


async def _make_card(
    recipient_email="bob@example.com",
    status="active",
    amount=1000,
    sender_name="Alice",
) -> GiftCard:
    raw_token, token_hash = generate_token()
    card = GiftCard(
        id=f"gc_{token_hash[:16]}",
        wallet="wallet_test",
        card_wallet_id=None,
        amount=amount,
        token_hash=token_hash,
        raw_token=raw_token,
        redemption_url=f"http://test/giftcards/redeem/{raw_token}",
        status=status,
        recipient_name="Bob",
        sender_name=sender_name,
        message="Hello",
        expires_at=None,
        created_at=datetime.now(timezone.utc),
        redeemed_at=None,
        expired_at=None,
        recipient_email=recipient_email,
    )
    await create_card(card)
    return card


# ===========================================================================
# Task 1: Magic link CRUD, claim endpoints, rate limiting, claim page
# ===========================================================================

# --- Magic link CRUD functions exist ---

def test_create_magic_link_exists():
    """create_magic_link function exists in crud.py."""
    from giftcards.crud import create_magic_link
    assert create_magic_link is not None


def test_get_magic_link_by_hash_exists():
    """get_magic_link_by_hash function exists in crud.py."""
    from giftcards.crud import get_magic_link_by_hash
    assert get_magic_link_by_hash is not None


def test_invalidate_magic_links_for_email_exists():
    """invalidate_magic_links_for_email function exists in crud.py."""
    from giftcards.crud import invalidate_magic_links_for_email
    assert invalidate_magic_links_for_email is not None


def test_get_pending_cards_by_email_exists():
    """get_pending_cards_by_email function exists in crud.py."""
    from giftcards.crud import get_pending_cards_by_email
    assert get_pending_cards_by_email is not None


def test_count_recent_magic_links_exists():
    """count_recent_magic_links function exists in crud.py."""
    from giftcards.crud import count_recent_magic_links
    assert count_recent_magic_links is not None


def test_mark_magic_link_used_exists():
    """mark_magic_link_used function exists in crud.py."""
    from giftcards.crud import mark_magic_link_used
    assert mark_magic_link_used is not None


def test_create_magic_link_is_async():
    """create_magic_link is an async function."""
    from giftcards.crud import create_magic_link
    assert inspect.iscoroutinefunction(create_magic_link)


def test_get_magic_link_by_hash_is_async():
    """get_magic_link_by_hash is an async function."""
    from giftcards.crud import get_magic_link_by_hash
    assert inspect.iscoroutinefunction(get_magic_link_by_hash)


def test_invalidate_magic_links_for_email_is_async():
    """invalidate_magic_links_for_email is an async function."""
    from giftcards.crud import invalidate_magic_links_for_email
    assert inspect.iscoroutinefunction(invalidate_magic_links_for_email)


def test_get_pending_cards_by_email_is_async():
    """get_pending_cards_by_email is an async function."""
    from giftcards.crud import get_pending_cards_by_email
    assert inspect.iscoroutinefunction(get_pending_cards_by_email)


def test_count_recent_magic_links_is_async():
    """count_recent_magic_links is an async function."""
    from giftcards.crud import count_recent_magic_links
    assert inspect.iscoroutinefunction(count_recent_magic_links)


def test_mark_magic_link_used_is_async():
    """mark_magic_link_used is an async function."""
    from giftcards.crud import mark_magic_link_used
    assert inspect.iscoroutinefunction(mark_magic_link_used)


# --- Magic link CRUD behavior ---

@pytest.mark.anyio
async def test_create_magic_link_returns_raw_token():
    """create_magic_link returns a raw token string (43 chars from token_urlsafe(32))."""
    await _reset_tables()
    from giftcards.crud import create_magic_link
    token = await create_magic_link("test@example.com", "wallet_test")
    assert isinstance(token, str)
    assert len(token) == 43  # secrets.token_urlsafe(32) produces 43 chars


@pytest.mark.anyio
async def test_create_magic_link_stores_hash_not_raw():
    """create_magic_link stores only the SHA-256 hash, not the raw token."""
    await _reset_tables()
    import hashlib
    from giftcards.crud import create_magic_link, get_magic_link_by_hash
    token = await create_magic_link("test@example.com", "wallet_test")
    expected_hash = hashlib.sha256(token.encode()).hexdigest()
    # Looking up by the hash should work
    link = await get_magic_link_by_hash(expected_hash)
    assert link is not None
    assert link.token_hash == expected_hash
    assert link.token_hash != token  # hash != raw token


@pytest.mark.anyio
async def test_count_recent_magic_links_zero():
    """count_recent_magic_links returns 0 for a new email."""
    await _reset_tables()
    from giftcards.crud import count_recent_magic_links
    count = await count_recent_magic_links("new@example.com")
    assert count == 0


@pytest.mark.anyio
async def test_count_recent_magic_links_after_create():
    """count_recent_magic_links increments after creating a link."""
    await _reset_tables()
    from giftcards.crud import create_magic_link, count_recent_magic_links
    await create_magic_link("count@example.com", "wallet_test")
    count = await count_recent_magic_links("count@example.com")
    assert count == 1


@pytest.mark.anyio
async def test_get_pending_cards_by_email():
    """get_pending_cards_by_email returns active cards with raw_token."""
    await _reset_tables()
    from giftcards.crud import get_pending_cards_by_email
    card = await _make_card(recipient_email="pending@example.com")
    cards = await get_pending_cards_by_email("pending@example.com")
    assert len(cards) == 1
    assert cards[0]["id"] == card.id
    assert "raw_token" in cards[0]
    assert cards[0]["raw_token"] == card.raw_token


@pytest.mark.anyio
async def test_get_pending_cards_excludes_redeemed():
    """get_pending_cards_by_email excludes redeemed cards."""
    await _reset_tables()
    from giftcards.crud import get_pending_cards_by_email
    await _make_card(recipient_email="filter@example.com", status="redeemed")
    cards = await get_pending_cards_by_email("filter@example.com")
    assert len(cards) == 0


@pytest.mark.anyio
async def test_get_pending_cards_excludes_expired():
    """get_pending_cards_by_email excludes expired cards."""
    await _reset_tables()
    from giftcards.crud import get_pending_cards_by_email
    await _make_card(recipient_email="filter2@example.com", status="expired")
    cards = await get_pending_cards_by_email("filter2@example.com")
    assert len(cards) == 0


@pytest.mark.anyio
async def test_invalidate_magic_links_deletes_rows():
    """invalidate_magic_links_for_email deletes all magic_links for an email."""
    await _reset_tables()
    from giftcards.crud import (
        create_magic_link,
        invalidate_magic_links_for_email,
        count_recent_magic_links,
    )
    await create_magic_link("invalidate@example.com", "wallet_test")
    await create_magic_link("invalidate@example.com", "wallet_test")
    assert await count_recent_magic_links("invalidate@example.com") == 2
    await invalidate_magic_links_for_email("invalidate@example.com")
    assert await count_recent_magic_links("invalidate@example.com") == 0


@pytest.mark.anyio
async def test_mark_magic_link_used_sets_used_at():
    """mark_magic_link_used sets the used_at timestamp."""
    await _reset_tables()
    import hashlib
    from giftcards.crud import create_magic_link, get_magic_link_by_hash, mark_magic_link_used
    token = await create_magic_link("used@example.com", "wallet_test")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Before marking, used_at should be None
    link = await get_magic_link_by_hash(token_hash)
    assert link.used_at is None
    # Mark as used
    await mark_magic_link_used(token_hash)
    # After marking, the link should not be returned (used_at IS NOT NULL)
    link2 = await get_magic_link_by_hash(token_hash)
    assert link2 is None


@pytest.mark.anyio
async def test_get_magic_link_by_hash_expired():
    """get_magic_link_by_hash returns None for expired links."""
    await _reset_tables()
    import hashlib
    from giftcards.crud import create_magic_link, get_magic_link_by_hash
    token = await create_magic_link("expired@example.com", "wallet_test")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Manually expire the link by setting expires_at to the past
    await db.execute(
        "UPDATE giftcards.magic_links SET expires_at = :past WHERE token_hash = :hash",
        {"past": datetime(2020, 1, 1, tzinfo=timezone.utc), "hash": token_hash},
    )
    link = await get_magic_link_by_hash(token_hash)
    assert link is None


# --- generate_magic_link service ---

def test_generate_magic_link_exists():
    """generate_magic_link function exists in services.py."""
    from giftcards.services import generate_magic_link
    assert generate_magic_link is not None


def test_generate_magic_link_is_async():
    """generate_magic_link is an async function."""
    from giftcards.services import generate_magic_link
    assert inspect.iscoroutinefunction(generate_magic_link)


@pytest.mark.anyio
async def test_generate_magic_link_returns_token():
    """generate_magic_link returns a raw token string."""
    await _reset_tables()
    from giftcards.services import generate_magic_link
    token = await generate_magic_link("gen@example.com", "wallet_test")
    assert isinstance(token, str)
    assert len(token) == 43


# --- Claim endpoints ---

def test_giftcards_claim_router_exists():
    """giftcards_claim_router exists in views_api.py."""
    from giftcards.views_api import giftcards_claim_router
    assert giftcards_claim_router is not None


def test_claim_router_has_two_routes():
    """giftcards_claim_router has at least 2 routes (POST and GET)."""
    from giftcards.views_api import giftcards_claim_router
    routes = list(giftcards_claim_router.routes)
    assert len(routes) >= 2


def test_claim_router_prefix():
    """giftcards_claim_router has prefix /api/v1/claim."""
    from giftcards.views_api import giftcards_claim_router
    assert giftcards_claim_router.prefix == "/api/v1/claim"


def test_claim_router_included_in_ext():
    """giftcards_ext includes giftcards_claim_router."""
    from giftcards import giftcards_ext
    # Check that the claim router's prefix appears in the ext's routes
    all_paths = []
    for route in giftcards_ext.routes:
        if hasattr(route, 'path'):
            all_paths.append(route.path)
    # The claim endpoints should be under /giftcards/api/v1/claim
    claim_paths = [p for p in all_paths if '/claim' in p]
    assert len(claim_paths) >= 2


# --- ClaimRequest model ---

def test_claim_request_model():
    """ClaimRequest model accepts email field."""
    req = ClaimRequest(email="test@example.com")
    assert req.email == "test@example.com"


# --- views.py claim routes ---

def test_views_py_has_claim_route():
    """views.py contains /claim route registration."""
    import giftcards.views as v
    source = inspect.getsource(v)
    assert "/claim" in source


# --- routes.json ---

def test_routes_json_has_claim():
    """routes.json contains claim route entries."""
    import json
    from pathlib import Path
    import giftcards
    routes_path = Path(giftcards.__file__).resolve().parent / "static" / "routes.json"
    routes = json.loads(routes_path.read_text())
    claim_routes = [r for r in routes if "claim" in r["path"]]
    assert len(claim_routes) >= 2


def test_routes_json_claim_names():
    """routes.json has PageGiftCardsClaim and PageGiftCardsClaimVerify route names."""
    import json
    from pathlib import Path
    import giftcards
    routes_path = Path(giftcards.__file__).resolve().parent / "static" / "routes.json"
    routes = json.loads(routes_path.read_text())
    names = [r.get("name", "") for r in routes]
    assert "PageGiftCardsClaim" in names
    assert "PageGiftCardsClaimVerify" in names


# --- claim.vue ---

def test_claim_vue_exists():
    """claim.vue file exists."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    assert path.exists()


def test_claim_vue_has_claim_heading():
    """claim.vue contains 'Claim Your Gift Card' heading."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    content = path.read_text()
    assert "Claim Your Gift Card" in content


def test_claim_vue_has_redeem_button():
    """claim.vue contains 'Redeem Gift Card' button text."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    content = path.read_text()
    assert "Redeem Gift Card" in content


def test_claim_vue_has_invalid_state():
    """claim.vue contains 'Link Invalid or Expired' text."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    content = path.read_text()
    assert "Link Invalid or Expired" in content


def test_claim_vue_has_check_email():
    """claim.vue contains 'Check Your Email' confirmation text."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    content = path.read_text()
    assert "Check Your Email" in content


def test_claim_vue_has_rate_limited():
    """claim.vue contains 'Too Many Requests' rate limit text."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.vue"
    content = path.read_text()
    assert "Too Many Requests" in content


# --- claim.js ---

def test_claim_js_exists():
    """claim.js file exists."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    assert path.exists()


def test_claim_js_has_submit_claim():
    """claim.js contains submitClaim method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    content = path.read_text()
    assert "submitClaim" in content


def test_claim_js_has_verify_magic_link():
    """claim.js contains verifyMagicLink method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    content = path.read_text()
    assert "verifyMagicLink" in content


def test_claim_js_has_reset_claim():
    """claim.js contains resetClaim method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    content = path.read_text()
    assert "resetClaim" in content


def test_claim_js_has_format_date():
    """claim.js contains formatDate method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    content = path.read_text()
    assert "formatDate" in content


def test_claim_js_posts_to_claim_api():
    """claim.js POSTs to /giftcards/api/v1/claim."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "claim.js"
    content = path.read_text()
    assert "/giftcards/api/v1/claim" in content


# --- lnurl_callback invalidation ---

def test_lnurl_callback_has_invalidation():
    """views_api.py lnurl_callback calls invalidate_magic_links_for_email."""
    import giftcards.views_api as v
    source = inspect.getsource(v)
    assert "invalidate_magic_links" in source


# ===========================================================================
# Task 2: Jinja2 email templates, SMTP send, deliver endpoint, email dialog
# ===========================================================================

# --- Email service functions ---

def test_render_email_template_exists():
    """render_email_template function exists in services.py."""
    from giftcards.services import render_email_template
    assert render_email_template is not None


def test_send_smtp_email_exists():
    """_send_smtp_email function exists in services.py."""
    from giftcards.services import _send_smtp_email
    assert _send_smtp_email is not None


def test_send_gift_card_email_exists():
    """send_gift_card_email function exists in services.py."""
    from giftcards.services import send_gift_card_email
    assert send_gift_card_email is not None


def test_send_notification_email_exists():
    """send_notification_email function exists in services.py."""
    from giftcards.services import send_notification_email
    assert send_notification_email is not None


def test_send_gift_card_email_is_async():
    """send_gift_card_email is an async function."""
    from giftcards.services import send_gift_card_email
    assert inspect.iscoroutinefunction(send_gift_card_email)


def test_send_notification_email_is_async():
    """send_notification_email is an async function."""
    from giftcards.services import send_notification_email
    assert inspect.iscoroutinefunction(send_notification_email)


def test_render_email_template_notification():
    """render_email_template renders notification.html with context variables."""
    from giftcards.services import render_email_template
    result = render_email_template(
        "notification.html",
        sender_name="Alice",
        magic_link_url="http://test/claim/token123",
        claim_url="http://test/claim",
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Alice" in result


def test_render_email_template_fancy():
    """render_email_template renders fancy.html with context variables."""
    from giftcards.services import render_email_template
    result = render_email_template(
        "fancy.html",
        sender_name="Alice",
        message="Happy birthday!",
        claim_url="http://test/claim",
        amount=50000,
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Alice" in result


def test_render_email_template_custom_text():
    """render_email_template renders custom_text.html with body variable."""
    from giftcards.services import render_email_template
    result = render_email_template(
        "custom_text.html",
        body="Hello from the sender!",
        claim_url="http://test/claim",
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Hello from the sender!" in result


# --- Email template files ---

def test_notification_html_exists():
    """notification.html template file exists."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "notification.html"
    assert path.exists()


def test_fancy_html_exists():
    """fancy.html template file exists."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "fancy.html"
    assert path.exists()


def test_custom_text_html_exists():
    """custom_text.html template file exists."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "custom_text.html"
    assert path.exists()


def test_notification_html_has_sender_name():
    """notification.html contains {{ sender_name }}."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "notification.html"
    content = path.read_text()
    assert "{{ sender_name }}" in content


def test_notification_html_has_magic_link_url():
    """notification.html contains {{ magic_link_url }}."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "notification.html"
    content = path.read_text()
    assert "{{ magic_link_url }}" in content


def test_fancy_html_has_claim_url():
    """fancy.html contains {{ claim_url }}."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "fancy.html"
    content = path.read_text()
    assert "{{ claim_url }}" in content


def test_fancy_html_has_amount():
    """fancy.html contains {{ amount }}."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "fancy.html"
    content = path.read_text()
    assert "{{ amount }}" in content


def test_custom_text_html_has_body():
    """custom_text.html contains {{ body }}."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "email_templates" / "custom_text.html"
    content = path.read_text()
    assert "{{ body }}" in content


# --- Deliver endpoint ---

def test_deliver_endpoint_registered():
    """giftcards_api_router has a route path containing 'deliver'."""
    from giftcards.views_api import giftcards_api_router
    routes = list(giftcards_api_router.routes)
    deliver_routes = [r for r in routes if hasattr(r, 'path') and 'deliver' in r.path]
    assert len(deliver_routes) >= 1


# --- DeliverRequest model ---

def test_deliver_request_model():
    """DeliverRequest model accepts recipient_email, email_mode, subject, body."""
    req = DeliverRequest(
        recipient_email="recipient@example.com",
        email_mode="custom",
        subject="Test subject",
        body="Test body",
    )
    assert req.recipient_email == "recipient@example.com"
    assert req.email_mode == "custom"
    assert req.subject == "Test subject"
    assert req.body == "Test body"


def test_deliver_request_defaults():
    """DeliverRequest model has correct defaults."""
    req = DeliverRequest(recipient_email="r@example.com")
    assert req.email_mode == "custom"
    assert req.subject is None
    assert req.body is None


# --- Email dialog in index.vue ---

def test_index_vue_has_send_email_dialog():
    """index.vue contains 'Send Gift Card Email' dialog heading."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.vue"
    content = path.read_text()
    assert "Send Gift Card Email" in content


def test_index_vue_has_email_mode_select():
    """index.vue contains email mode select."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.vue"
    content = path.read_text()
    assert "Email Mode" in content


# --- Email dialog methods in index.js ---

def test_index_js_has_open_email_dialog():
    """index.js contains openEmailDialog method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = path.read_text()
    assert "openEmailDialog" in content


def test_index_js_has_send_email():
    """index.js contains sendEmail method."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = path.read_text()
    assert "sendEmail" in content


def test_index_js_email_dialog_posts_to_deliver():
    """index.js sendEmail posts to /deliver endpoint."""
    from pathlib import Path
    import giftcards
    path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = path.read_text()
    assert "/deliver" in content


# --- Token generation security ---

def test_magic_link_token_is_43_chars():
    """Magic link token from secrets.token_urlsafe(32) is 43 characters."""
    import secrets
    token = secrets.token_urlsafe(32)
    assert len(token) == 43


def test_magic_link_hash_is_64_hex():
    """SHA-256 hash of magic link token is 64 hex characters."""
    import hashlib
    import secrets
    token = secrets.token_urlsafe(32)
    hash_val = hashlib.sha256(token.encode()).hexdigest()
    assert len(hash_val) == 64
    assert all(c in "0123456789abcdef" for c in hash_val)
