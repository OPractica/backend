import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.voice import VoiceRecord

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).resolve().parents[3] / "audio_storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

RETENTION_HOURS = 24
ALLOWED_LANGUAGES = {"ru", "ro", "en", "auto"}


async def save_voice_record(
    session: AsyncSession,
    audio_path: Path,
    text: str,
    language: str,
) -> VoiceRecord:
    """Save recording metadata with a 24-hour expiration."""

    audio_path = Path(audio_path)

    if not audio_path.is_file():
        raise FileNotFoundError("Audio file not found")

    if audio_path.resolve().parent != STORAGE_DIR.resolve():
        raise ValueError("Audio file must be inside the storage directory")

    if not text.strip():
        raise ValueError("Transcription cannot be empty")

    if language not in ALLOWED_LANGUAGES:
        raise ValueError("Unsupported language")

    now = datetime.now(UTC)

    record = VoiceRecord(
        audio_path=audio_path.name,
        transcription=text.strip(),
        language=language,
        created_at=now,
        expires_at=now + timedelta(hours=RETENTION_HOURS),
    )

    try:
        session.add(record)
        await session.flush()
        await session.refresh(record)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return record


async def delete_expired_records() -> int:
    """Remove expired audio files and their database records."""

    now = datetime.now(UTC)
    deleted_count = 0

    async with SessionLocal() as session:
        records = (
            await session.scalars(
                select(VoiceRecord).where(VoiceRecord.expires_at <= now)
            )
        ).all()

        try:
            for record in records:
                filename = record.audio_path

                if (
                    not filename
                    or filename in {".", ".."}
                    or Path(filename).name != filename
                ):
                    logger.warning(
                        "Invalid audio filename in record %s",
                        record.id,
                    )
                    continue

                file_path = STORAGE_DIR / filename

                try:
                    await asyncio.to_thread(
                        file_path.unlink,
                        missing_ok=True,
                    )
                except OSError:
                    logger.exception(
                        "Failed to remove audio for record %s",
                        record.id,
                    )
                    continue

                await session.delete(record)
                deleted_count += 1

            await session.commit()

        except Exception:
            await session.rollback()
            logger.exception("Voice cleanup database operation failed")
            raise

    return deleted_count
