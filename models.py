import re
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, validator, root_validator

# Allowlists for filesystem-interpolated design fields (H-1: path traversal defense)
ALLOWED_FONTS = {"DejaVuSans", "DejaVuSerif", "DejaVuSansMono"}
ALLOWED_TEMPLATES = {"portrait", "landscape", "custom"}
ALLOWED_TEXT_ALIGN = {"left", "center", "right"}
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Bech32 npub format: starts with "npub1", followed by alphanumeric chars, total ~62-64
_NPUB_RE = re.compile(r"^npub1[023456789acdefghjklmnpqrstuvwxyz]{58,60}$")


def _normalize_email(v: Optional[str]) -> Optional[str]:
    """Normalize email to lowercase, stripped. None passes through."""
    if v is None:
        return None
    return v.strip().lower()


class DesignConfig(BaseModel):
    """Design configuration for branded card image rendering."""
    template_asset_id: Optional[str] = None
    template_name: str = "portrait"
    qr_x_frac: float = 0.1
    qr_y_frac: float = 0.7
    qr_size: int = 200
    text_x_frac: float = 0.1
    text_y_frac: float = 0.1
    font_family: str = "DejaVuSans"
    font_size: int = 24
    font_color: str = "#000000"
    bg_color: Optional[str] = None
    text_align: str = "left"
    show_amount: bool = True
    show_recipient: bool = True
    show_message: bool = True

    @validator("template_name")
    def _validate_template_name(cls, v):
        # H-1: prevent path traversal via template_name (interpolated into filesystem path)
        if v not in ALLOWED_TEMPLATES:
            raise ValueError(
                f"Invalid template_name; must be one of {sorted(ALLOWED_TEMPLATES)}"
            )
        return v

    @validator("font_family")
    def _validate_font_family(cls, v):
        # H-1: prevent path traversal via font_family (interpolated into filesystem path)
        if v not in ALLOWED_FONTS:
            raise ValueError(
                f"Invalid font_family; must be one of {sorted(ALLOWED_FONTS)}"
            )
        return v

    @validator("font_color")
    def _validate_font_color(cls, v):
        # M-6: validate hex color so the public render endpoint cannot 500 on junk
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("font_color must be a #RRGGBB hex color")
        return v

    @validator("bg_color")
    def _validate_bg_color(cls, v):
        # M-6: validate hex color (optional) for portrait/landscape background fill
        if v is None or v == "":
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("bg_color must be a #RRGGBB hex color")
        return v

    @validator("text_align")
    def _validate_text_align(cls, v):
        if v not in ALLOWED_TEXT_ALIGN:
            raise ValueError(
                f"Invalid text_align; must be one of {sorted(ALLOWED_TEXT_ALIGN)}"
            )
        return v

    @validator("qr_x_frac", "qr_y_frac", "text_x_frac", "text_y_frac")
    def _validate_frac(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError("fraction coordinates must be between 0.0 and 1.0")
        return v

    @validator("qr_size")
    def _validate_qr_size(cls, v):
        if v < 150:
            raise ValueError("qr_size must be >= 150 (minimum scannable size)")
        return v


class MagicLink(BaseModel):
    """Magic link for email verification flow."""
    id: str
    token_hash: str
    email: str
    wallet: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None


class ClaimRequest(BaseModel):
    """Request body for claim endpoint."""
    email: str

    @validator("email")
    def _normalize_email(cls, v):
        # M-1: normalize to lowercase so rate limit / lookup cannot be bypassed by case
        return _normalize_email(v) or ""


class DeliverRequest(BaseModel):
    """Request body for email delivery endpoint."""
    recipient_email: str
    email_mode: str = "custom"
    subject: Optional[str] = None
    body: Optional[str] = None
    template: Optional[str] = None
    bg_color: Optional[str] = None

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        # M-1: normalize stored recipient email to lowercase for consistent lookup
        return _normalize_email(v) or ""

    @validator("bg_color")
    def _validate_bg_color(cls, v):
        if v is None or v == "":
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("bg_color must be a #RRGGBB hex color")
        return v


class CreateGiftCard(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in sats")
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        # M-1: normalize stored recipient email to lowercase for consistent lookup
        return _normalize_email(v)

    @validator("expires_at", pre=True)
    def parse_expires_at(cls, v):
        """Accept date-only strings (from HTML <input type="date">) and convert to datetime."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle date-only format: "2026-07-05" -> end of that day
            if len(v) == 10 and v.count("-") == 2:
                return datetime.fromisoformat(v + "T23:59:59+00:00")
            # Handle datetime strings without timezone -> assume UTC
            try:
                dt = datetime.fromisoformat(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        return v


class GiftCard(BaseModel):
    id: str
    wallet: str
    card_wallet_id: Optional[str]
    amount: int
    token_hash: str
    raw_token: Optional[str] = None
    redemption_url: Optional[str] = None
    status: str  # active, redeeming, redeemed, expired
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_at: Optional[datetime]
    expired_at: Optional[datetime]
    template_asset_id: Optional[str] = None
    template_name: Optional[str] = None
    qr_config: Optional[str] = None
    text_config: Optional[str] = None
    recipient_email: Optional[str] = None
    email_status: str = "not_sent"
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    email_template: Optional[str] = None


class GiftCardSummary(BaseModel):
    id: str
    amount: int
    status: str
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_at: Optional[datetime]
    expired_at: Optional[datetime]
    redemption_url: Optional[str] = None
    recipient_email: Optional[str] = None
    email_status: Optional[str] = None


class PublicGiftCard(BaseModel):
    status: str
    amount: int
    sender_name: Optional[str]
    recipient_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    expired_at: Optional[datetime]
    has_design: bool = False


class CreateGiftCardResponse(BaseModel):
    card: GiftCardSummary
    raw_token: str
    redemption_url: str
    lnurl_url: str


class CSVRow(BaseModel):
    """A single row from a CSV bulk upload file.

    Per D-05 — required: recipient_name, amount_sats; optional: rest.
    Per D-06 — per-row design columns map to DesignConfig fields.
    """
    row_num: int
    recipient_name: str
    amount_sats: int = Field(..., gt=0)
    recipient_email: Optional[str] = None
    nostr_npub: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    template_name: Optional[str] = None
    qr_x_frac: Optional[float] = None
    qr_y_frac: Optional[float] = None
    qr_size: Optional[int] = None
    text_x_frac: Optional[float] = None
    text_y_frac: Optional[float] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    bg_color: Optional[str] = None
    text_align: Optional[str] = None

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        return _normalize_email(v)

    @validator("amount_sats")
    def _positive_amount(cls, v):
        if v <= 0:
            raise ValueError("amount_sats must be greater than 0")
        return v

    @validator("nostr_npub")
    def _validate_npub(cls, v):
        if v is None or v == "":
            return None
        if not _NPUB_RE.match(v):
            raise ValueError("Invalid npub format")
        return v

    @validator("template_name")
    def _validate_template_name(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_TEMPLATES:
            raise ValueError(
                f"Invalid template_name; must be one of {sorted(ALLOWED_TEMPLATES)}"
            )
        return v

    @validator("font_family")
    def _validate_font_family(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_FONTS:
            raise ValueError(
                f"Invalid font_family; must be one of {sorted(ALLOWED_FONTS)}"
            )
        return v

    @validator("font_color")
    def _validate_font_color(cls, v):
        if v is None or v == "":
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("font_color must be a #RRGGBB hex color")
        return v

    @validator("bg_color")
    def _validate_bg_color(cls, v):
        if v is None or v == "":
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("bg_color must be a #RRGGBB hex color")
        return v

    @validator("text_align")
    def _validate_text_align(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_TEXT_ALIGN:
            raise ValueError(
                f"Invalid text_align; must be one of {sorted(ALLOWED_TEXT_ALIGN)}"
            )
        return v


class CSVValidationError(BaseModel):
    """A single validation error from a CSV row."""
    row_num: int
    field: str
    message: str


class CSVValidationResult(BaseModel):
    """Result of validating a CSV file — per-row validation table + summary.

    Per D-07.
    """
    valid_count: int
    error_count: int
    valid_rows: List[CSVRow] = []
    errors: List[CSVValidationError] = []


class UpdateCardRequest(BaseModel):
    """Request body for PUT /cards/{card_id}.

    Per D-15 — amount is NOT editable (requires cancel + recreate).
    All other metadata fields are directly editable.
    The optional `design` field allows updating the card's template and
    card design (QR position, text styling, background color, etc.).
    Set `clear_design=True` to remove an existing design (bare QR card).
    """
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None
    clear_design: bool = False

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        return _normalize_email(v)


class BulkCreateRequest(BaseModel):
    """Request body for bulk gift card creation.

    Per D-02 (number input for quantity) and D-08 (500 row max).
    Supports two modes:
    - Same-amount mode: count + amount (both required)
    - CSV mode: rows (list of CSVRow) + design_mode (count/amount optional)
    """
    count: Optional[int] = Field(None, gt=0, le=500, description="Number of cards to create (max 500)")
    amount: Optional[int] = Field(None, gt=0, description="Amount in sats for each card")
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    recipient_email: Optional[str] = None
    design: Optional[DesignConfig] = None
    rows: Optional[List[CSVRow]] = None
    design_mode: Optional[str] = None

    @validator("count")
    def _max_count(cls, v):
        if v is not None and v > 500:
            raise ValueError("count must be at most 500")
        return v

    @validator("amount")
    def _positive_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @validator("recipient_email")
    def _normalize_recipient_email(cls, v):
        return _normalize_email(v)

    @root_validator
    def _validate_mode(cls, values):
        count = values.get("count")
        amount = values.get("amount")
        rows = values.get("rows")
        # Either (count AND amount) OR rows must be provided
        has_same_amount = count is not None and amount is not None
        has_csv = rows is not None and len(rows) > 0
        if not has_same_amount and not has_csv:
            raise ValueError(
                "Provide either count+amount for same-amount bulk, or rows for CSV bulk"
            )
        return values

    @validator("expires_at", pre=True)
    def parse_expires_at(cls, v):
        """Accept date-only strings (from HTML <input type="date">) and convert to datetime."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            if len(v) == 10 and v.count("-") == 2:
                return datetime.fromisoformat(v + "T23:59:59+00:00")
            try:
                dt = datetime.fromisoformat(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        return v


class BulkDeleteRequest(BaseModel):
    """Request body for DELETE /cards/bulk.

    Per D-16 — bulk delete selected cards, reclaiming sats for any
    active cards and skipping redeemed cards.
    """
    card_ids: List[str] = Field(..., min_items=1, max_items=500)


class CardDetailResponse(BaseModel):
    """Detail response for GET /cards/{card_id}.

    Per D-11 — redemption_url defaults to None, only populated when
    include_link=true is explicitly passed.
    Includes the parsed design config so the edit dialog can populate
    the card designer with the card's current template and styling.
    """
    card_id: str
    amount: int
    status: str
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    recipient_email: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    redeemed_at: Optional[datetime] = None
    email_status: Optional[str] = None
    token_hash: Optional[str] = None
    redemption_url: Optional[str] = None
    design: Optional[DesignConfig] = None
