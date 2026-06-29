from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class CreateGiftCard(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in sats")
    recipient_name: Optional[str] = None
    sender_name: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


class GiftCard(BaseModel):
    id: str
    wallet: str
    card_wallet_id: Optional[str]
    amount: int
    token_hash: str
    status: str  # active, redeeming, redeemed, expired
    recipient_name: Optional[str]
    sender_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_at: Optional[datetime]
    expired_at: Optional[datetime]


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


class PublicGiftCard(BaseModel):
    status: str
    amount: int
    sender_name: Optional[str]
    recipient_name: Optional[str]
    message: Optional[str]
    expires_at: Optional[datetime]
    expired_at: Optional[datetime]


class CreateGiftCardResponse(BaseModel):
    card: GiftCardSummary
    raw_token: str
    redemption_url: str
    lnurl_url: str