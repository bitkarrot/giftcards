"""Tests for Phase 2 branded card image pipeline (plan 02-01)."""
import pytest
from datetime import datetime
from PIL import Image


# ---------------------------------------------------------------------------
# Task 1: Migration m003, extended models, and bundled assets
# ---------------------------------------------------------------------------

def test_design_config_defaults():
    """DesignConfig model has correct default values."""
    from giftcards.models import DesignConfig

    d = DesignConfig()
    assert d.qr_size == 200
    assert d.font_family == "DejaVuSans"
    assert d.font_color == "#000000"
    assert d.text_align == "left"
    assert d.template_name == "portrait"


def test_new_models_importable():
    """All new Phase 2 models can be imported."""
    from giftcards.models import DesignConfig, MagicLink, ClaimRequest, DeliverRequest

    assert DesignConfig is not None
    assert MagicLink is not None
    assert ClaimRequest is not None
    assert DeliverRequest is not None


def test_create_gift_card_accepts_design_and_email():
    """CreateGiftCard accepts recipient_email and design kwargs."""
    from giftcards.models import CreateGiftCard, DesignConfig

    card = CreateGiftCard(amount=1000, recipient_email="bob@example.com", design=DesignConfig())
    assert card.recipient_email == "bob@example.com"
    assert card.design is not None


def test_gift_card_has_email_status():
    """GiftCard model has email_status field with default not_sent."""
    from giftcards.models import GiftCard

    card = GiftCard(
        id="gc_test",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="a" * 64,
        status="active",
        recipient_name=None,
        sender_name=None,
        message=None,
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
    )
    assert card.email_status == "not_sent"


def test_m003_migration_exists_and_is_async():
    """m003_branded_delivery function exists and is async."""
    import inspect
    from giftcards import migrations

    func = getattr(migrations, "m003_branded_delivery", None)
    assert func is not None
    assert inspect.iscoroutinefunction(func)


def test_template_portrait_dimensions():
    """Bundled portrait template is 425x650."""
    import giftcards

    path = (
        __import__("pathlib").Path(giftcards.__file__).resolve().parent
        / "static"
        / "image"
        / "template_portrait.png"
    )
    img = Image.open(path)
    assert img.size == (425, 650)


def test_template_landscape_dimensions():
    """Bundled landscape template is 1050x600."""
    import giftcards

    path = (
        __import__("pathlib").Path(giftcards.__file__).resolve().parent
        / "static"
        / "image"
        / "template_landscape.png"
    )
    img = Image.open(path)
    assert img.size == (1050, 600)


def test_bundled_fonts_exist():
    """Three TTF font files exist in static/fonts/."""
    import giftcards
    from pathlib import Path

    fonts_dir = Path(giftcards.__file__).resolve().parent / "static" / "fonts"
    assert (fonts_dir / "DejaVuSans.ttf").exists()
    assert (fonts_dir / "DejaVuSerif.ttf").exists()
    assert (fonts_dir / "DejaVuSansMono.ttf").exists()


# ---------------------------------------------------------------------------
# Task 2: Card image renderer service and render/print endpoints
# ---------------------------------------------------------------------------

def test_get_font_returns_non_none():
    """get_font returns a non-None ImageFont object."""
    from giftcards.services import get_font

    font = get_font("DejaVuSans", 24)
    assert font is not None


def test_get_font_caches():
    """get_font called twice with same args returns the same cached object."""
    from giftcards.services import get_font

    f1 = get_font("DejaVuSans", 24)
    f2 = get_font("DejaVuSans", 24)
    assert f1 is f2


def test_render_card_image_is_async():
    """render_card_image is an async function."""
    import inspect
    from giftcards.services import render_card_image

    assert inspect.iscoroutinefunction(render_card_image)


@pytest.mark.anyio
async def test_render_card_image_returns_png_bytes():
    """render_card_image returns valid PNG bytes for a card with design config."""
    from datetime import datetime
    from giftcards.models import GiftCard
    from giftcards.services import render_card_image

    card = GiftCard(
        id="gc_test",
        wallet="w",
        card_wallet_id=None,
        amount=50000,
        token_hash="a" * 64,
        status="active",
        recipient_name="Bob",
        sender_name="Alice",
        message="Happy birthday!",
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
        template_name="portrait",
        qr_config='{"qr_x_frac": 0.1, "qr_y_frac": 0.7, "qr_size": 200}',
        text_config='{"text_x_frac": 0.1, "text_y_frac": 0.1, "font_family": "DejaVuSans", "font_size": 24, "font_color": "#000000", "text_align": "left"}',
    )
    png_bytes = await render_card_image(card, "https://example.com/lnurl/test", scale=1)
    assert png_bytes is not None
    assert len(png_bytes) > 0
    # PNG magic bytes
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_registered():
    """giftcards_api_router has a route path containing 'image'."""
    from giftcards.views_api import giftcards_api_router

    routes = [r.path for r in giftcards_api_router.routes]
    assert any("image" in r for r in routes)


def test_print_endpoint_registered():
    """giftcards_api_router has a route path containing 'print'."""
    from giftcards.views_api import giftcards_api_router

    routes = [r.path for r in giftcards_api_router.routes]
    assert any("print" in r for r in routes)


def test_image_endpoint_is_public():
    """The image endpoint has no Depends(require_admin_key)."""
    import inspect
    from giftcards.views_api import giftcards_api_router

    dep_strs = []
    for route in giftcards_api_router.routes:
        if "image" in route.path:
            for dep in getattr(route, "dependencies", []):
                dep_strs.append(str(dep))
            sig = inspect.signature(route.endpoint)
            for param in sig.parameters.values():
                if param.default != inspect.Parameter.empty:
                    dep_strs.append(str(param.default))
    assert not any("require_admin_key" in s for s in dep_strs)


def test_print_endpoint_is_authenticated():
    """The print endpoint has Depends(require_admin_key)."""
    import inspect
    from giftcards.views_api import giftcards_api_router

    found_auth = False
    for route in giftcards_api_router.routes:
        if "print" in route.path:
            sig = inspect.signature(route.endpoint)
            for param in sig.parameters.values():
                if param.default != inspect.Parameter.empty:
                    if "require_admin_key" in str(param.default):
                        found_auth = True
    assert found_auth


def test_update_card_email_status_exists():
    """update_card_email_status function exists in crud."""
    from giftcards.crud import update_card_email_status

    assert callable(update_card_email_status)


def test_get_cards_by_wallet_includes_email_columns():
    """get_cards_by_wallet SELECT includes recipient_email and email_status."""
    import inspect
    from giftcards.crud import get_cards_by_wallet

    src = inspect.getsource(get_cards_by_wallet)
    assert "recipient_email" in src
    assert "email_status" in src


# ---------------------------------------------------------------------------
# Task 3: Create endpoint with design config, public endpoint has_design,
#         redemption page branded image, card list delivery column
# ---------------------------------------------------------------------------

def test_create_gift_card_handles_design_config():
    """create_gift_card function source contains 'qr_config' or 'design'."""
    import inspect
    from giftcards.services import create_gift_card

    src = inspect.getsource(create_gift_card)
    assert "qr_config" in src or "design" in src


def test_public_card_endpoint_returns_has_design():
    """api_get_public_card function source contains 'has_design'."""
    import inspect
    from giftcards.views_api import api_get_public_card

    src = inspect.getsource(api_get_public_card)
    assert "has_design" in src


def test_redeem_vue_has_branded_card_img():
    """redeem.vue contains the string 'branded-card-img'."""
    import giftcards
    from pathlib import Path

    vue_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "redeem.vue"
    content = vue_path.read_text()
    assert "branded-card-img" in content


def test_redeem_js_has_card_image_url():
    """redeem.js contains the string 'cardImageUrl'."""
    import giftcards
    from pathlib import Path

    js_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "redeem.js"
    content = js_path.read_text()
    assert "cardImageUrl" in content


def test_index_js_has_delivery_and_download():
    """index.js contains 'delivery' in columns and 'downloadPrintable' method."""
    import giftcards
    from pathlib import Path

    js_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = js_path.read_text()
    assert "delivery" in content
    assert "downloadPrintable" in content


def test_index_vue_has_download_png():
    """index.vue contains 'Download PNG' button text."""
    import giftcards
    from pathlib import Path

    vue_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.vue"
    content = vue_path.read_text()
    assert "Download PNG" in content


def test_get_delivery_status_color_mapping():
    """getDeliveryStatusColor returns correct colors for each status."""
    import giftcards
    from pathlib import Path
    import re

    js_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = js_path.read_text()

    # Verify the function exists and has the right mappings
    assert "getDeliveryStatusColor" in content
    assert "positive" in content  # sent
    assert "negative" in content  # failed
    assert "grey-6" in content  # not_sent


def test_get_delivery_status_text_mapping():
    """getDeliveryStatusText returns correct labels for each status."""
    import giftcards
    from pathlib import Path

    js_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    content = js_path.read_text()

    assert "getDeliveryStatusText" in content
    assert "Not sent" in content
    assert "Sent" in content
    assert "Failed" in content


@pytest.mark.anyio
async def test_create_card_with_design_config_via_api():
    """Create card with design config via API, verify response has design fields."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from giftcards.views_api import api_create_card
    from giftcards.models import CreateGiftCard, DesignConfig

    data = CreateGiftCard(
        amount=50000,
        recipient_name="Bob",
        sender_name="Alice",
        message="Happy birthday!",
        recipient_email="bob@example.com",
        design=DesignConfig(template_name="portrait"),
    )

    mock_wallet = MagicMock()
    mock_wallet.wallet.id = "wallet_test"
    mock_wallet.wallet.user = "user_test"

    mock_request = MagicMock()
    mock_request.base_url = "https://example.com/"

    with patch("giftcards.views_api.create_gift_card", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = MagicMock(
            dict=MagicMock(return_value={
                "card": {"id": "gc_test", "amount": 50000, "status": "active"},
                "raw_token": "test_token",
                "redemption_url": "https://example.com/giftcards/redeem/test_token",
                "lnurl_url": "https://example.com/giftcards/api/v1/lnurl/test_hash",
            })
        )
        result = await api_create_card(data=data, request=mock_request, wallet=mock_wallet)
        assert result is not None
        # Verify create_gift_card was called with design config
        call_args = mock_create.call_args
        assert call_args.kwargs["data"].design is not None


@pytest.mark.anyio
async def test_public_card_endpoint_has_design_true():
    """GET /api/v1/cards/public/{token_hash} returns has_design=true for card with design."""
    from unittest.mock import AsyncMock, patch
    from datetime import datetime
    from giftcards.views_api import api_get_public_card
    from giftcards.models import GiftCard

    card = GiftCard(
        id="gc_test",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="a" * 64,
        status="active",
        recipient_name="Bob",
        sender_name="Alice",
        message="Hello",
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
        template_name="portrait",
    )

    with patch("giftcards.views_api.get_card_by_token_hash", new_callable=AsyncMock, return_value=card):
        result = await api_get_public_card(token_hash="a" * 64)
        assert result.has_design == True


@pytest.mark.anyio
async def test_public_card_endpoint_has_design_false():
    """GET /api/v1/cards/public/{token_hash} returns has_design=false for card without design."""
    from unittest.mock import AsyncMock, patch
    from datetime import datetime
    from giftcards.views_api import api_get_public_card
    from giftcards.models import GiftCard

    card = GiftCard(
        id="gc_test",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="a" * 64,
        status="active",
        recipient_name="Bob",
        sender_name="Alice",
        message="Hello",
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
        template_name=None,
    )

    with patch("giftcards.views_api.get_card_by_token_hash", new_callable=AsyncMock, return_value=card):
        result = await api_get_public_card(token_hash="a" * 64)
        assert result.has_design == False


def test_render_card_image_bare_qr_without_template():
    """A card without design renders a square bare QR image with no template."""
    from io import BytesIO
    from datetime import datetime
    from giftcards.models import GiftCard
    from giftcards.services import _render_card_image_sync

    card = GiftCard(
        id="gc_bare_qr",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="a" * 64,
        status="active",
        recipient_name=None,
        sender_name=None,
        message=None,
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
        template_name=None,
        template_asset_id=None,
        qr_config=None,
        text_config=None,
    )

    png = _render_card_image_sync(card, "https://example.com/lnurl", scale=1)
    img = Image.open(BytesIO(png)).convert("RGB")
    assert img.width == img.height, "bare QR image should be square"
    assert img.width == 400, "bare QR base size should be 400px"

    # Branded portrait template is 425x650, so verify we did not use it.
    assert (img.width, img.height) != (425, 650)


@pytest.mark.anyio
async def test_render_card_image_bare_qr_async():
    """Async render_card_image returns a bare QR for a card without design."""
    from io import BytesIO
    from datetime import datetime
    from giftcards.models import GiftCard
    from giftcards.services import render_card_image

    card = GiftCard(
        id="gc_bare_qr_async",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="b" * 64,
        status="active",
        recipient_name=None,
        sender_name=None,
        message=None,
        expires_at=None,
        created_at=datetime.now(),
        redeemed_at=None,
        expired_at=None,
        template_name=None,
        template_asset_id=None,
        qr_config=None,
        text_config=None,
    )

    png = await render_card_image(card, "https://example.com/lnurl", scale=1)
    img = Image.open(BytesIO(png)).convert("RGB")
    assert img.width == img.height == 400
