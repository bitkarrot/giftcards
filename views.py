from fastapi import APIRouter, Depends
from lnbits.core.views.generic import index, index_public
from lnbits.decorators import check_user_exists

giftcards_generic_router = APIRouter()


giftcards_generic_router.add_api_route(
    "/",
    methods=["GET"],
    endpoint=index,
    dependencies=[Depends(check_user_exists)],
)


giftcards_generic_router.add_api_route(
    "/redeem/{raw_token}",
    methods=["GET"],
    endpoint=index_public,
)