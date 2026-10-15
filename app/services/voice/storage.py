import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.voice import VoiceRecord

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
STORAGE_DIR = BASE_DIR / "audio_storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

RETENTION_HOURS = 24


async def save_voice_record(
    session: AsyncSession,
    audio_path: Path,
    text: str,
    language: str,
) -> VoiceRecord:
    now = datetime.now(UTC)

    record = VoiceRecord(
        audio_path=audio_path.name,
        transcription=text,
        language=language,
        created_at=now,
        expires_at=now + timedelta(hours=RETENTION_HOURS),
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record


async def delete_expired_records() -> int:
    now = datetime.now(UTC)
    deleted = 0

    async with SessionLocal() as session:
        records = (
            await session.scalars(
                select(VoiceRecord).where(VoiceRecord.expires_at <= now)
            )
        ).all()

        for record in records:
            filename = Path(record.audio_path).name

            if filename != record.audio_path:
                logger.warning("Unsafe audio path in record %s", record.id)
                continue

            file_path = STORAGE_DIR / filename

            try:
                await asyncio.to_thread(
                    file_path.unlink,
                    missing_ok=True,
                )
            except OSError:
                logger.exception(
                    "Failed to delete audio file for record %s",
                    record.id,
                )
                continue

            await session.delete(record)
            deleted += 1

        await session.commit()

    return deleted
