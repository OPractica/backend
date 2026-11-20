import asyncio
import logging
import re
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
    *,
    user_id: int,
) -> VoiceRecord:
    """Save an authenticated user's recording with 24-hour retention."""

    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")

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
        user_id=user_id,
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


PENDING_RECOVERY_GRACE_SECONDS = 3600
# Give active uploads/transcriptions time to finish before cleaning crashed requests.
ORPHAN_AUDIO_GRACE_SECONDS = 24 * 60 * 60
# Only consider filenames created by save_uploaded_audio(), never arbitrary files.
UPLOADED_AUDIO_NAME = re.compile(
    r"[0-9a-f]{32}\.(?:flac|mp3|mp4|mpeg|mpga|m4a|ogg|wav|webm)"
)


async def _recover_pending_audio(session: AsyncSession) -> None:
    """Recover old interrupted cleanup operations."""

    now_timestamp = datetime.now(UTC).timestamp()

    for staged in STORAGE_DIR.glob(".*.pending"):
        try:
            if staged.is_symlink() or not staged.is_file():
                continue

            stem = staged.name[1 : -len(".pending")]
            original_and_stamp, separator, token = stem.rpartition(".")

            if (
                not separator
                or len(token) != 32
                or any(char not in "0123456789abcdef" for char in token)
            ):
                continue

            original_name, separator, stamp = original_and_stamp.rpartition(".")

            if separator and stamp.startswith("ts-") and stamp[3:].isdigit():
                created_at = float(stamp[3:])
            else:
                # Compatibility with previously staged filenames.
                original_name = original_and_stamp
                created_at = staged.stat().st_mtime

            if (
                not original_name
                or original_name in {".", ".."}
                or Path(original_name).name != original_name
            ):
                continue

            age = now_timestamp - created_at

            if age < PENDING_RECOVERY_GRACE_SECONDS:
                continue

            original = STORAGE_DIR / original_name

            record_id = await session.scalar(
                select(VoiceRecord.id)
                .where(VoiceRecord.audio_path == original_name)
                .limit(1)
            )

            if record_id is not None:
                if original.exists():
                    logger.warning(
                        "Cannot restore pending audio: original exists: %s",
                        original_name,
                    )
                    continue

                await asyncio.to_thread(staged.rename, original)
                logger.info("Restored pending audio: %s", original_name)

            else:
                await asyncio.to_thread(
                    staged.unlink,
                    missing_ok=True,
                )
                logger.info("Removed orphan pending audio: %s", staged.name)

        except OSError:
            logger.exception(
                "Could not recover pending audio: %s",
                staged.name,
            )


async def _remove_orphaned_audio(session: AsyncSession) -> None:
    """Delete old managed uploads that have no database record."""

    cutoff = datetime.now(UTC).timestamp() - ORPHAN_AUDIO_GRACE_SECONDS

    for audio_path in STORAGE_DIR.iterdir():
        if UPLOADED_AUDIO_NAME.fullmatch(audio_path.name) is None:
            continue

        try:
            # Never follow a link or touch a directory.
            if audio_path.is_symlink() or not audio_path.is_file():
                continue

            if audio_path.stat().st_mtime >= cutoff:
                continue

            record_id = await session.scalar(
                select(VoiceRecord.id)
                .where(VoiceRecord.audio_path == audio_path.name)
                .limit(1)
            )
            if record_id is not None:
                continue

            await asyncio.to_thread(audio_path.unlink)
            logger.info("Removed orphaned voice upload: %s", audio_path.name)

        except FileNotFoundError:
            # Another cleanup worker may have deleted this file first.
            continue
        except OSError:
            logger.exception("Could not clean orphaned audio: %s", audio_path.name)


async def delete_expired_records() -> int:
    """Remove expired records with recoverable audio staging."""

    from uuid import uuid4

    now = datetime.now(UTC)
    staged_files: list[tuple[Path, Path, int]] = []
    deleted_count = 0

    async with SessionLocal() as session:
        await _recover_pending_audio(session)
        await _remove_orphaned_audio(session)

        records = (
            await session.scalars(
                select(VoiceRecord)
                .where(VoiceRecord.expires_at <= now)
                .with_for_update(skip_locked=True)
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

                original = STORAGE_DIR / filename
                staged = STORAGE_DIR / (
                    f".{filename}.ts-{int(now.timestamp())}.{uuid4().hex}.pending"
                )

                try:
                    await asyncio.to_thread(
                        original.replace,
                        staged,
                    )
                except FileNotFoundError:
                    # The audio is already missing; remove stale metadata.
                    pass
                except OSError:
                    logger.exception(
                        "Cannot stage audio for record %s",
                        record.id,
                    )
                    continue
                else:
                    staged_files.append((original, staged, record.id))

                await session.delete(record)
                deleted_count += 1

            await session.commit()

        except (Exception, asyncio.CancelledError):
            try:
                await session.rollback()
            finally:
                for original, staged, record_id in reversed(staged_files):
                    try:
                        await asyncio.to_thread(
                            staged.replace,
                            original,
                        )
                    except OSError:
                        logger.exception(
                            "Failed to restore audio for record %s",
                            record_id,
                        )
            raise

    # Delete staged files only after database commit succeeds.
    for _, staged, record_id in staged_files:
        try:
            await asyncio.to_thread(
                staged.unlink,
                missing_ok=True,
            )
        except OSError:
            logger.exception(
                "Failed to delete staged audio for record %s",
                record_id,
            )

    return deleted_count
