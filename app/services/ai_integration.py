import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prompts.loader import get_system_prompt
from app.services.rag.availability import find_matching_available_seats
from app.services.rag.context import render_seat_context
from app.services.rag.search import SearchMode, search_seats
from app.services.voice.transcribe import transcribe_audio


async def process_user_text(
    text: str,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> dict:
    has_start = starts_at is not None
    has_end = ends_at is not None

    if has_start != has_end:
        raise ValueError("Both starts_at and ends_at are required")

    if has_start:
        if mode != "database":
            raise ValueError("Availability checks require database mode")
        if session is None:
            raise ValueError("Availability checks require AsyncSession")

        result = await find_matching_available_seats(
            session=session,
            starts_at=starts_at,
            ends_at=ends_at,
            text=text,
            language=language,
        )
    else:
        result = await search_seats(
            text=text,
            language=language,
            session=session,
            mode=mode,
        )

    return {
        "text": text,
        "language": language,
        "preferences": result["preferences"],
        "needs_clarification": result["preferences"]["needs_clarification"],
        "seat_candidates": result["matches"],
        "context": render_seat_context(result),
        "system_prompt": get_system_prompt(language),
        "data_source": result["data_source"],
        "availability_checked": result["availability_checked"],
        "booking_created": False,
        "starts_at": starts_at.isoformat() if starts_at else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
    }


async def process_user_audio(
    file_path: str | Path,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> dict:
    text = await asyncio.to_thread(
        transcribe_audio,
        file_path,
        language,
    )
    return await process_user_text(
        text=text,
        language=language,
        session=session,
        mode=mode,
        starts_at=starts_at,
        ends_at=ends_at,
    )
