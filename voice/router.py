
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from voice.storage import STORAGE_DIR, save_voice_record
from voice.transcribe_audio import transcribe_audio

router = APIRouter(prefix="/ai", tags=["Voice"])

ALLOWED_FORMATS = {".mp3", ".wav", ".m4a"}
ALLOWED_LANGUAGES = {"ru", "ro", "en"}
MAX_FILE_SIZE = 25 * 1024 * 1024


@router.post("/voice")
async def recognize_voice(
    file: UploadFile = File(...),
    language: str | None = Form(None),
):
    if language is not None and language not in ALLOWED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(400, "Unsupported audio format")

    audio_path = STORAGE_DIR / f"{uuid4().hex}{suffix}"
    saved = False

    try:
        size = 0

        with audio_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        413, "Audio file is too large"
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(400, "Empty audio file")

        text = await asyncio.to_thread(
            transcribe_audio,
            str(audio_path),
            language,
        )

        record = await asyncio.to_thread(
            save_voice_record,
            audio_path,
            text,
            language or "auto",
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

    except Exception:
        raise HTTPException(
            502, "Voice processing failed"
        )

    finally:
        await file.close()

        if not saved:
            audio_path.unlink(missing_ok=True)
