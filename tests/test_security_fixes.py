"""Regression tests for Phase 2 code-review security fixes (H-1..H-4, M-1, M-2, M-6).

These tests verify the fixes for blocking HIGH and adjacent MEDIUM findings
from the post-execution code review. They are intentionally focused on the
security surface and do not re-test general functionality covered elsewhere.
"""
import pytest


# ---------------------------------------------------------------------------
# H-1: Path traversal in font_family / template_name (CWE-22)
# ---------------------------------------------------------------------------

def test_design_config_rejects_traversal_font_family():
    """H-1: font_family is interpolated into a filesystem path; must be allowlisted."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(font_family="../../../../tmp/evil")


def test_design_config_rejects_traversal_template_name():
    """H-1: template_name is interpolated into a filesystem path; must be allowlisted."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(template_name="../../etc/passwd")


def test_design_config_rejects_unknown_font():
    """H-1: non-allowlisted font family is rejected."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(font_family="ComicSans")


def test_design_config_rejects_unknown_template():
    """H-1: non-allowlisted template name is rejected."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(template_name="square")


def test_design_config_accepts_all_allowed_fonts():
    """H-1: every allowlisted font family is accepted."""
    from giftcards.models import DesignConfig, ALLOWED_FONTS

    for font in ALLOWED_FONTS:
        d = DesignConfig(font_family=font)
        assert d.font_family == font


def test_design_config_accepts_all_allowed_templates():
    """H-1: every allowlisted template name is accepted."""
    from giftcards.models import DesignConfig, ALLOWED_TEMPLATES

    for tmpl in ALLOWED_TEMPLATES:
        d = DesignConfig(template_name=tmpl)
        assert d.template_name == tmpl


# ---------------------------------------------------------------------------
# M-6: font_color must be #RRGGBB hex
# ---------------------------------------------------------------------------

def test_design_config_rejects_invalid_font_color():
    """M-6: non-hex font_color is rejected (prevents 500 on public render endpoint)."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(font_color="rm -rf /")


def test_design_config_rejects_short_hex_font_color():
    """M-6: #RGB (3-digit) is rejected — only #RRGGBB accepted."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(font_color="#FFF")


def test_design_config_accepts_valid_hex_font_color():
    """M-6: valid #RRGGBB hex is accepted (upper and lower case)."""
    from giftcards.models import DesignConfig

    assert DesignConfig(font_color="#000000").font_color == "#000000"
    assert DesignConfig(font_color="#FFaA30").font_color == "#FFaA30"


# ---------------------------------------------------------------------------
# M-1: Email case-sensitivity normalization (rate limit bypass defense)
# ---------------------------------------------------------------------------

def test_claim_request_normalizes_email_to_lowercase():
    """M-1: ClaimRequest.email is normalized to lowercase to prevent rate-limit bypass."""
    from giftcards.models import ClaimRequest

    req = ClaimRequest(email="Bob@Example.COM")
    assert req.email == "bob@example.com"


def test_claim_request_strips_email_whitespace():
    """M-1: ClaimRequest.email strips surrounding whitespace."""
    from giftcards.models import ClaimRequest

    req = ClaimRequest(email="  bob@example.com  ")
    assert req.email == "bob@example.com"


def test_deliver_request_normalizes_recipient_email():
    """M-1: DeliverRequest.recipient_email is normalized to lowercase."""
    from giftcards.models import DeliverRequest

    req = DeliverRequest(recipient_email="Alice@Example.com")
    assert req.recipient_email == "alice@example.com"


def test_create_gift_card_normalizes_recipient_email():
    """M-1: CreateGiftCard.recipient_email is normalized to lowercase for consistent storage."""
    from giftcards.models import CreateGiftCard

    card = CreateGiftCard(amount=1000, recipient_email="Mixed@Case.COM")
    assert card.recipient_email == "mixed@case.com"


# ---------------------------------------------------------------------------
# H-2: Magic link single-use race condition (atomic mark-used)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_mark_magic_link_used_if_unused_returns_true_for_unused(monkeypatch):
    """H-2: mark_magic_link_used_if_unused returns True when it claims an unused link."""
    from giftcards import crud

    class FakeResult:
        rowcount = 1

    async def fake_execute(*args, **kwargs):
        return FakeResult()

    monkeypatch.setattr(crud.db, "execute", fake_execute)
    claimed = await crud.mark_magic_link_used_if_unused("somehash")
    assert claimed is True


@pytest.mark.anyio
async def test_mark_magic_link_used_if_unused_returns_false_for_already_used(monkeypatch):
    """H-2: mark_magic_link_used_if_unused returns False when the link is already used."""
    from giftcards import crud

    class FakeResult:
        rowcount = 0  # no rows updated — already used

    async def fake_execute(*args, **kwargs):
        return FakeResult()

    monkeypatch.setattr(crud.db, "execute", fake_execute)
    claimed = await crud.mark_magic_link_used_if_unused("somehash")
    assert claimed is False


@pytest.mark.anyio
async def test_mark_magic_link_used_if_unused_sql_includes_used_at_is_null(monkeypatch):
    """H-2: the UPDATE statement must include `used_at IS NULL` guard for atomicity."""
    from giftcards import crud

    captured = {}

    class FakeResult:
        rowcount = 1

    async def fake_execute(query, params):
        captured["query"] = query
        captured["params"] = params
        return FakeResult()

    monkeypatch.setattr(crud.db, "execute", fake_execute)
    await crud.mark_magic_link_used_if_unused("abc123")
    # The SQL must contain the atomic guard
    assert "used_at IS NULL" in captured["query"]


# ---------------------------------------------------------------------------
# H-4: Internal error detail not leaked to client
# ---------------------------------------------------------------------------

def test_deliver_email_endpoint_does_not_leak_exception_detail():
    """H-4: the deliver endpoint returns a generic 500 message, not str(exc).

    We verify by checking the source that the exception string is not passed
    to HTTPException(detail=...).
    """
    import inspect
    from giftcards.views_api import api_deliver_email

    source = inspect.getsource(api_deliver_email)
    # The generic message must be present
    assert "Email delivery failed. Check server logs." in source
    # The dangerous pattern detail=str(exc) must NOT be present
    assert "detail=str(exc)" not in source
    assert "detail=f" not in source


# ---------------------------------------------------------------------------
# H-3: Email sent to updated recipient (in-memory sync)
# ---------------------------------------------------------------------------

def test_deliver_email_syncs_in_memory_recipient():
    """H-3: the deliver endpoint sets card.recipient_email on the in-memory object
    after the DB update so send_gift_card_email addresses the NEW recipient.
    """
    import inspect
    from giftcards.views_api import api_deliver_email

    source = inspect.getsource(api_deliver_email)
    # The fix assigns data.recipient_email back to the in-memory card object
    assert "card.recipient_email = data.recipient_email" in source


# ---------------------------------------------------------------------------
# M-2: Fire-and-forget SMTP (timing-based email enumeration defense)
# ---------------------------------------------------------------------------

def test_claim_endpoint_uses_background_task_for_smtp():
    """M-2: the claim endpoint dispatches the notification email via
    asyncio.create_task so response latency does not leak whether cards exist.
    """
    import inspect
    from giftcards.views_api import api_claim_cards

    source = inspect.getsource(api_claim_cards)
    assert "asyncio.create_task" in source
    # Must NOT await the send inline (which would create a timing leak)
    assert "await send_notification_email" not in source


# ---------------------------------------------------------------------------
# DesignConfig fraction coordinate validation (bonus hardening)
# ---------------------------------------------------------------------------

def test_design_config_rejects_negative_frac():
    """Fraction coordinates must be in [0.0, 1.0]."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(qr_x_frac=-0.1)


def test_design_config_rejects_over_one_frac():
    """Fraction coordinates must be in [0.0, 1.0]."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(text_y_frac=1.5)


def test_design_config_rejects_invalid_text_align():
    """text_align must be in the allowlist."""
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(text_align="justify")


# ---------------------------------------------------------------------------
# show_text toggle (UAT enhancement: optional amount/recipient/message)
# ---------------------------------------------------------------------------

def test_design_config_show_text_defaults_true():
    """show_text defaults to True (backward compatible with existing cards)."""
    from giftcards.models import DesignConfig

    assert DesignConfig().show_text is True


def test_design_config_accepts_show_text_false():
    """show_text=False is accepted and stored."""
    from giftcards.models import DesignConfig

    assert DesignConfig(show_text=False).show_text is False


def test_parse_design_config_reads_show_text():
    """_parse_design_config reads show_text from the text_config JSON column."""
    import json
    from giftcards.models import GiftCard
    from giftcards.services import _parse_design_config

    card = GiftCard(
        id="test",
        wallet="w",
        card_wallet_id=None,
        amount=1000,
        token_hash="h",
        raw_token=None,
        redemption_url=None,
        status="active",
        recipient_name=None,
        sender_name=None,
        message=None,
        expires_at=None,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        redeemed_at=None,
        expired_at=None,
        template_asset_id=None,
        template_name="portrait",
        qr_config=json.dumps({"qr_x_frac": 0.1, "qr_y_frac": 0.7, "qr_size": 200}),
        text_config=json.dumps({"show_text": False}),
        recipient_email=None,
        email_status="not_sent",
        email_subject=None,
        email_body=None,
        email_template=None,
    )
    design = _parse_design_config(card)
    assert design.show_text is False


def test_render_card_image_omits_text_when_show_text_false():
    """The renderer must not draw any text when show_text=False.

    We verify by rendering two images (show_text True vs False) and checking
    that the show_text=False image has fewer distinct colors (text pixels
    are absent).
    """
    import json
    from datetime import datetime, timezone
    from giftcards.models import GiftCard
    from giftcards.services import _render_card_image_sync

    def _make_card(show_text: bool) -> GiftCard:
        return GiftCard(
            id=f"t{int(show_text)}",
            wallet="w",
            card_wallet_id=None,
            amount=1000,
            token_hash=f"h{int(show_text)}",
            raw_token=None,
            redemption_url=None,
            status="active",
            recipient_name="Alice",
            sender_name="Bob",
            message="Hello",
            expires_at=None,
            created_at=datetime.now(timezone.utc),
            redeemed_at=None,
            expired_at=None,
            template_asset_id=None,
            template_name="portrait",
            qr_config=json.dumps({"qr_x_frac": 0.1, "qr_y_frac": 0.7, "qr_size": 200}),
            text_config=json.dumps({
                "text_x_frac": 0.1,
                "text_y_frac": 0.1,
                "font_family": "DejaVuSans",
                "font_size": 48,
                "font_color": "#000000",
                "text_align": "left",
                "show_text": show_text,
            }),
            recipient_email=None,
            email_status="not_sent",
            email_subject=None,
            email_body=None,
            email_template=None,
        )

    png_with = _render_card_image_sync(_make_card(True), "https://example.com/x", scale=1)
    png_without = _render_card_image_sync(_make_card(False), "https://example.com/x", scale=1)

    from PIL import Image
    from io import BytesIO
    img_with = Image.open(BytesIO(png_with)).convert("RGB")
    img_without = Image.open(BytesIO(png_without)).convert("RGB")
    colors_with = len(set(img_with.getcolors(maxcolors=1000000)) or [])
    colors_without = len(set(img_without.getcolors(maxcolors=1000000)) or [])
    # The image WITH text must have more distinct colors than the one WITHOUT
    # (text adds black pixels at many anti-aliased shades).
    assert colors_with > colors_without, (
        f"expected show_text=True to produce more colors than False, "
        f"got {colors_with} vs {colors_without}"
    )
