import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import http_exception_handler, validation_exception_handler
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.health import router as health_router
from app.api.v1.meeting import router as meeting_router
from app.api.v1.seats import router as seats_router
from app.api.v1.voice import router as voice_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.booking import auto_cancel_checkin, cleanup_cancelled_bookings
from app.services.voice.body_limit import VoiceBodyLimitMiddleware
from app.services.voice.storage import delete_expired_records

logger = logging.getLogger(__name__)

CHECKIN_INTERVAL_SECONDS = 60
BOOKING_CLEANUP_INTERVAL_SECONDS = 86400
VOICE_CLEANUP_INTERVAL_SECONDS = 60


async def periodic_checkin() -> None:
    """Automatically cancel unconfirmed bookings."""
    while True:
        try:
            async with SessionLocal() as session:
                await auto_cancel_checkin(session)
                await session.commit()
        except Exception:
            logger.exception("Failed to auto-cancel unconfirmed bookings")

        await asyncio.sleep(CHECKIN_INTERVAL_SECONDS)


async def periodic_cleanup() -> None:
    """Periodically remove old cancelled bookings."""
    while True:
        try:
            async with SessionLocal() as session:
                await cleanup_cancelled_bookings(session)
                await session.commit()
        except Exception:
            logger.exception("Failed to clean up old cancelled bookings")

        await asyncio.sleep(BOOKING_CLEANUP_INTERVAL_SECONDS)


async def periodic_voice_cleanup() -> None:
    """Periodically delete expired voice recordings and database records."""
    while True:
        try:
            deleted_count = await delete_expired_records()

            if deleted_count:
                logger.info(
                    "Deleted %d expired voice records",
                    deleted_count,
                )
        except Exception:
            logger.exception("Failed to clean up expired voice records")

        await asyncio.sleep(VOICE_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and gracefully stop periodic maintenance tasks."""
    tasks = [
        asyncio.create_task(periodic_checkin(), name="periodic_checkin"),
        asyncio.create_task(periodic_cleanup(), name="periodic_cleanup"),
        asyncio.create_task(
            periodic_voice_cleanup(),
            name="periodic_voice_cleanup",
        ),
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


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
app.include_router(meeting_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.add_middleware(VoiceBodyLimitMiddleware)
