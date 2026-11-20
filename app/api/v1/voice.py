import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile, status
from groq import APIConnectionError, APIStatusError, RateLimitError
from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from app.api.deps import CurrentUser
from app.api.errors import APIError
from app.api.openapi import AUTH_RESPONSES
from app.core.db import SessionDep
from app.schemas.voice import VoiceProcessingResult, VoiceTranscriptionResponse
from app.services.voice.process import process_voice_preferences
from app.services.voice.storage import save_voice_record
from app.services.voice.upload import (
    AudioTooLargeError,
    InvalidAudioError,
    save_uploaded_audio,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

Language = Literal["auto", "ru", "ro", "en"]


def voice_error(
    status_code: int,
    detail: str,
    code: str,
) -> APIError:
    return APIError(
        status_code=status_code,
        detail=detail,
        code=code,
    )


@router.post(
    "/transcribe",
    response_model=VoiceTranscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transcribe audio and extract workspace preferences",
    description=(
        "Upload an audio recording in Russian, Romanian, or English. "
        "The service transcribes speech, detects the language, "
        "extracts workspace preferences, and stores the recording "
        "with a 24-hour expiration. It does not create bookings."
    ),
    responses={
        413: {"description": "Audio file is too large"},
        415: {"description": "Unsupported audio format"},
        422: {"description": "Audio cannot be transcribed"},
        429: {"description": "Transcription provider rate limit"},
        503: {"description": "Voice service unavailable"},
        **AUTH_RESPONSES,
    },
)
async def transcribe_voice(
    file: Annotated[
        UploadFile,
        File(description="Audio recording to transcribe"),
    ],
    current_user: CurrentUser,
    session: SessionDep,
    language: Annotated[Language, Form()] = "auto",
) -> VoiceTranscriptionResponse:
    """Process audio without triggering any booking actions."""

    audio_path: Path | None = None
    saved = False

    try:
        try:
            audio_path = await save_uploaded_audio(file)

        except AudioTooLargeError:
            raise voice_error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "audio file is too large",
                "audio_too_large",
            ) from None

        except InvalidAudioError:
            raise voice_error(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "unsupported or invalid audio file",
                "invalid_audio",
            ) from None

        processing_task = asyncio.create_task(
            asyncio.to_thread(
                process_voice_preferences,
                audio_path,
                language,
            )
        )

        try:
            result = await asyncio.shield(processing_task)

        except asyncio.CancelledError:
            # A cancelled request does not stop the running thread.
            # Keep the audio file until the worker has finished.
            while not processing_task.done():
                try:
                    await asyncio.shield(processing_task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    logger.exception("Voice worker failed during request cancellation")
                    break

            try:
                processing_task.result()
            except Exception:
                logger.exception("Voice processing failed after request cancellation")

            raise

        except RateLimitError:
            raise voice_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "transcription service is busy, try again later",
                "voice_busy",
            ) from None

        except APIConnectionError:
            raise voice_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "transcription service is unavailable",
                "voice_unavailable",
            ) from None

        except APIStatusError as exc:
            if exc.status_code in {400, 413, 415, 422}:
                raise voice_error(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "audio could not be processed",
                    "audio_unprocessable",
                ) from None

            raise voice_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "transcription service is unavailable",
                "voice_unavailable",
            ) from None

        except ValueError:
            raise voice_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "audio contains no usable speech or supported language",
                "transcription_invalid",
            ) from None

        try:
            processed = VoiceProcessingResult.model_validate(result)
            processed_data = processed.model_dump(mode="json")
        except (ValidationError, PydanticSerializationError):
            logger.exception("Voice processor returned invalid data")
            raise voice_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "voice processing returned invalid data",
                "voice_processing_invalid",
            ) from None

        saving_task = asyncio.create_task(
            save_voice_record(
                session=session,
                audio_path=audio_path,
                text=processed.transcription,
                language=processed.language,
                user_id=current_user.id,
            )
        )

        try:
            record = await asyncio.shield(saving_task)

        except asyncio.CancelledError:
            # The database operation must finish before file cleanup.
            while not saving_task.done():
                try:
                    await asyncio.shield(saving_task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    logger.exception("Voice save failed after request cancellation")
                    break

            if (
                saving_task.done()
                and not saving_task.cancelled()
                and saving_task.exception() is None
            ):
                # The save completed successfully: keep its audio file.
                saved = True

            raise

        except Exception:
            logger.exception("Failed to save voice record metadata")
            raise voice_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "voice recording could not be saved",
                "voice_storage_unavailable",
            ) from None

        else:
            saved = True

        return VoiceTranscriptionResponse(
            record_id=record.id,
            expires_at=record.expires_at,
            **processed_data,
        )

    finally:
        await file.close()

        if audio_path is not None and not saved:
            with suppress(OSError):
                await asyncio.to_thread(
                    audio_path.unlink,
                    missing_ok=True,
                )
