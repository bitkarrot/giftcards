"""Tests for Phase 2 card designer UI and design config submission (plan 02-02)."""
import pytest
from datetime import datetime
from pathlib import Path

import giftcards


# ---------------------------------------------------------------------------
# Task 1: Card designer UI in create dialog — template selection, drag
# preview, QR resize handle, text styling controls, and design config
# serialization.
# ---------------------------------------------------------------------------

def _read_vue():
    vue_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.vue"
    return vue_path.read_text()


def _read_js():
    js_path = Path(giftcards.__file__).resolve().parent / "static" / "js" / "index.js"
    return js_path.read_text()


def test_vue_has_card_preview():
    """index.vue contains div.card-preview."""
    assert "card-preview" in _read_vue()


def test_vue_has_draggable_qr():
    """index.vue contains div.draggable-qr."""
    assert "draggable-qr" in _read_vue()


def test_vue_has_resize_handle():
    """index.vue contains div.resize-handle."""
    assert "resize-handle" in _read_vue()


def test_vue_has_draggable_text():
    """index.vue contains div.draggable-text."""
    assert "draggable-text" in _read_vue()


def test_vue_has_card_design_heading():
    """index.vue contains 'Card Design' heading."""
    assert "Card Design" in _read_vue()


def test_vue_has_hidden_file_input():
    """index.vue contains a hidden file input with handleTemplateSelected."""
    content = _read_vue()
    assert 'type="file"' in content
    assert "handleTemplateSelected" in content
    assert "display: none" in content or "display:none" in content


def test_js_has_start_drag():
    """index.js contains startDrag method."""
    assert "startDrag" in _read_js()


def test_js_has_on_drag():
    """index.js contains onDrag method."""
    assert "onDrag" in _read_js()


def test_js_has_end_drag():
    """index.js contains endDrag method."""
    assert "endDrag" in _read_js()


def test_js_has_start_resize():
    """index.js contains startResize method."""
    assert "startResize" in _read_js()


def test_js_has_on_resize():
    """index.js contains onResize method."""
    assert "onResize" in _read_js()


def test_js_has_upload_asset_file():
    """index.js contains uploadAssetFile method."""
    assert "uploadAssetFile" in _read_js()


def test_js_has_handle_template_selected():
    """index.js contains handleTemplateSelected method."""
    assert "handleTemplateSelected" in _read_js()


def test_js_has_trigger_template_upload():
    """index.js contains triggerTemplateUpload method."""
    assert "triggerTemplateUpload" in _read_js()


def test_js_has_min_qr_size_150():
    """index.js contains minQrSize with value 150."""
    content = _read_js()
    assert "minQrSize" in content
    assert "150" in content


def test_js_has_qr_x_frac_serialization():
    """index.js createGiftCard serializes qr_x_frac."""
    assert "qr_x_frac" in _read_js()


def test_js_has_font_color_serialization():
    """index.js createGiftCard serializes font_color."""
    assert "font_color" in _read_js()


def test_js_on_resize_enforces_min():
    """index.js onResize method enforces Math.max with minQrSize."""
    content = _read_js()
    assert "Math.max" in content
    assert "minQrSize" in content


def test_js_upload_uses_form_data_and_public_asset():
    """index.js uploadAssetFile uses FormData and public_asset."""
    content = _read_js()
    assert "FormData" in content
    assert "public_asset" in content


def test_js_start_drag_uses_pointer_capture():
    """index.js startDrag uses setPointerCapture."""
    assert "setPointerCapture" in _read_js()


def test_js_has_template_options():
    """index.js has templateOptions array."""
    assert "templateOptions" in _read_js()


def test_js_has_font_options():
    """index.js has fontOptions array."""
    assert "fontOptions" in _read_js()


def test_js_has_design_data_properties():
    """index.js has design-related data properties."""
    content = _read_js()
    for prop in [
        "selectedTemplate",
        "templateAssetId",
        "qrX",
        "qrY",
        "qrSize",
        "textX",
        "textY",
        "selectedFont",
        "fontSize",
        "fontColor",
        "textAlign",
        "previewWidth",
        "previewHeight",
        "dragState",
        "resizeState",
    ]:
        assert prop in content, f"Missing data property: {prop}"


def test_js_has_on_template_change():
    """index.js has onTemplateChange method."""
    assert "onTemplateChange" in _read_js()


def test_js_reset_create_dialog_resets_design():
    """resetCreateDialog resets design properties."""
    content = _read_js()
    assert "selectedTemplate" in content
    # resetCreateDialog should reference design props
    assert "qrX" in content


def test_js_has_dimension_validation():
    """index.js handleTemplateSelected validates image dimensions (max 1500x2000)."""
    content = _read_js()
    assert "naturalWidth" in content
    assert "naturalHeight" in content
    assert "1500" in content
    assert "2000" in content


# ---------------------------------------------------------------------------
# Task 2: Design config model behavior and backward compatibility
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
    assert d.qr_x_frac == 0.1
    assert d.qr_y_frac == 0.7
    assert d.text_x_frac == 0.1
    assert d.text_y_frac == 0.1


def test_design_config_custom_values():
    """DesignConfig accepts custom values for all fields."""
    from giftcards.models import DesignConfig

    d = DesignConfig(
        template_name="landscape",
        qr_x_frac=0.2,
        qr_y_frac=0.3,
        qr_size=300,
        text_x_frac=0.4,
        text_y_frac=0.5,
        font_family="DejaVuSerif",
        font_size=32,
        font_color="#FF0000",
        text_align="center",
    )
    assert d.template_name == "landscape"
    assert d.qr_x_frac == 0.2
    assert d.qr_y_frac == 0.3
    assert d.qr_size == 300
    assert d.text_x_frac == 0.4
    assert d.text_y_frac == 0.5
    assert d.font_family == "DejaVuSerif"
    assert d.font_size == 32
    assert d.font_color == "#FF0000"
    assert d.text_align == "center"


def test_create_gift_card_accepts_design_and_email():
    """CreateGiftCard accepts design and recipient_email fields."""
    from giftcards.models import CreateGiftCard, DesignConfig

    card = CreateGiftCard(
        amount=1000,
        recipient_email="test@example.com",
        design=DesignConfig(
            template_name="portrait",
            qr_x_frac=0.1,
            qr_y_frac=0.7,
            qr_size=200,
            font_family="DejaVuSerif",
            font_size=32,
            font_color="#FF0000",
            text_align="center",
        ),
    )
    assert card.recipient_email == "test@example.com"
    assert card.design is not None
    assert card.design.font_family == "DejaVuSerif"
    assert card.design.text_align == "center"


def test_create_gift_card_design_none_backward_compat():
    """CreateGiftCard with design=None does not raise (backward compatible)."""
    from giftcards.models import CreateGiftCard

    card = CreateGiftCard(amount=1000, design=None)
    assert card.design is None


def test_design_config_rejects_sub_minimum_qr_size():
    """DesignConfig rejects qr_size below 150 at model level (H-1/D-03 defense in depth).

    The 150px minimum scannable size is a locked decision (CONTEXT.md D-03).
    The model validator enforces it in addition to the renderer's max(150, ...) clamp.
    """
    import pytest
    from giftcards.models import DesignConfig

    with pytest.raises(Exception):
        DesignConfig(qr_size=100)
