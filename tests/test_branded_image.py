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
