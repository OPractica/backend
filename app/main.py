import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.v1 import health, voice
from app.services.voice.storage import delete_expired_records

logger = logging.getLogger(__name__)


async def cleanup_worker():
    """Periodically delete expired voice recordings."""
    while True:
        try:
            deleted = await delete_expired_records()

            if deleted:
                logger.info(
                    "Deleted %s expired voice records",
                    deleted,
                )
        except Exception:
            logger.exception("Voice cleanup failed")

        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_worker())

    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Office Booking API",
    version="0.1.0",
    lifespan=lifespan,
)

# Existing team routes
app.include_router(health.router, prefix="/api/v1")

# Voice recognition
app.include_router(voice.router, prefix="/api/v1")
