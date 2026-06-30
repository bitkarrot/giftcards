from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, validator


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
    text_align: str = "left"


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


class DeliverRequest(BaseModel):
    """Request body for email delivery endpoint."""
    recipient_email: str
    email_mode: str = "custom"
    subject: Optional[str] = None
    body: Optional[str] = None
    template: Optional[str] = None


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