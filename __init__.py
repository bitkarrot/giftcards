import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_expiry
from .views import giftcards_generic_router
from .views_api import giftcards_api_router, giftcards_lnurl_router

giftcards_ext: APIRouter = APIRouter(prefix="/giftcards", tags=["GiftCards"])
giftcards_ext.include_router(giftcards_generic_router)
giftcards_ext.include_router(giftcards_api_router)
giftcards_ext.include_router(giftcards_lnurl_router)

giftcards_static_files = [
    {
        "path": "/giftcards/static",
        "name": "giftcards_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def giftcards_stop():
    """Stop background tasks."""
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def giftcards_start():
    """Start background tasks."""
    from lnbits.tasks import create_permanent_unique_task

    # Start expiry sweep task (D-09, D-10)
    task = create_permanent_unique_task("ext_giftcards", wait_for_expiry)
    scheduled_tasks.append(task)


__all__ = ["db", "giftcards_ext", "giftcards_start", "giftcards_static_files", "giftcards_stop"]