import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prompts.loader import get_system_prompt
from app.services.rag.context import render_seat_context
from app.services.rag.search import SearchMode, search_seats
from app.services.voice.transcribe import transcribe_audio


async def process_user_text(
    text: str,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
) -> dict:
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
        "seat_candidates": result["matches"],
        "context": render_seat_context(result),
        "system_prompt": get_system_prompt(language),
        "data_source": result["data_source"],
        "availability_checked": False,
        "booking_created": False,
    }


async def process_user_audio(
    file_path: str | Path,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
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
    )
