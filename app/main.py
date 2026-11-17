import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import http_exception_handler, validation_exception_handler
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.health import router as health_router
from app.api.v1.seats import router as seats_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.booking import auto_cancel_checkin, cleanup_cancelled_bookings

logger = logging.getLogger(__name__)


async def periodic_checkin():
    while True:
        try:
            async with SessionLocal() as session:
                await auto_cancel_checkin(session)
                await session.commit()
        except Exception:
            logger.exception("Failed to auto-cancel unconfirmed bookings")
        await asyncio.sleep(60)


async def periodic_cleanup():
    while True:
        try:
            async with SessionLocal() as session:
                await cleanup_cancelled_bookings(session)
                await session.commit()
        except Exception:
            logger.exception("Failed to clean up old cancelled bookings")
        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cancel_task = asyncio.create_task(periodic_checkin())
    cleanup_task = asyncio.create_task(periodic_cleanup())
    yield
    cancel_task.cancel()
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cancel_task
        await cleanup_task


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(seats_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
