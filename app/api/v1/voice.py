
import asyncio
import logging
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.db import SessionDep
from app.services.voice.storage import STORAGE_DIR, save_voice_record
from app.services.voice.transcribe import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["Voice"])

ALLOWED_FORMATS = {".mp3", ".wav", ".m4a"}
ALLOWED_LANGUAGES = {"ru", "ro", "en"}
MAX_FILE_SIZE = 25 * 1024 * 1024


@router.post("/voice")
async def recognize_voice(
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    language: Annotated[str | None, Form()] = None,
):
    """Recognize and temporarily store an audio recording."""

    if language is not None and language not in ALLOWED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported language. Use ru, ro or en.",
        )

    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format.",
        )

    audio_path = STORAGE_DIR / f"{uuid4().hex}{suffix}"
    saved = False

    try:
        size = 0

        with audio_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio file exceeds 25 MB.",
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Audio file is empty.",
            )

        text = await asyncio.to_thread(
            transcribe_audio,
            audio_path,
            language,
        )

        record = await save_voice_record(
            session=session,
            audio_path=audio_path,
            text=text,
            language=language or "auto",
        )

        saved = True

        return {
            "status": "success",
            "record_id": record.id,
            "text": text,
            "language": language or "auto",
            "expires_at": record.expires_at.isoformat(),
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.error(
            "Voice processing failed: %s",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail="Voice processing failed.",
        ) from exc

    finally:
        await file.close()

        if not saved:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Failed to remove temporary audio file."
                )
