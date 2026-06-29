from fastapi import APIRouter

giftcards_generic_router = APIRouter()


@giftcards_generic_router.get("/")
async def index():
    """Serve the issuer SPA page."""
    # LNBits will serve the Vue SPA from the static directory
    return {"message": "Gift Cards Extension"}


@giftcards_generic_router.get("/redeem/{raw_token}")
async def index_public(raw_token: str):
    """Serve the public redemption SPA page."""
    # LNBits will serve the Vue SPA from the static directory
    return {"message": "Public Gift Card Redemption"}