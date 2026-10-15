import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from preferences.parser import extract_preferences
from rag.search import search_seats
from voice.router import router as voice_router
from voice.storage import (
    delete_expired_records,
    init_voice_database,
)


async def cleanup_worker():
    while True:
        try:
            deleted = await asyncio.to_thread(delete_expired_records)
            if deleted:
                print(f"Expired voice records deleted: {deleted}")
        except Exception:
            # Retry on the next cleanup cycle.
            import logging

            logging.getLogger(__name__).exception("Voice cleanup failed")

        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_voice_database)

    cleanup_task = asyncio.create_task(cleanup_worker())

    try:
        yield
    finally:
        cleanup_task.cancel()

        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="Voice Office Booking API",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(voice_router)


@app.get("/health")
def health():
    return {"status": "ok"}


class PreferenceRequest(BaseModel):
    text: str
    language: str = "ru"


@app.post("/ai/preferences")
def parse_preferences(request: PreferenceRequest):
    try:
        result = extract_preferences(
            request.text,
            request.language,
        )
        return result
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="Unsupported language",
        )


class SeatSearchRequest(BaseModel):
    text: str
    language: str = "ru"


@app.post("/ai/search-seats")
def search_seats_endpoint(request: SeatSearchRequest):
    try:
        return search_seats(
            text=request.text,
            language=request.language,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unsupported language",
        )
