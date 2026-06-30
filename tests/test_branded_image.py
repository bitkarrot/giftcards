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
