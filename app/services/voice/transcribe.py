from dataclasses import dataclass
from pathlib import Path

from groq import Groq

from app.core.config import settings

WHISPER_MODEL = "whisper-large-v3-turbo"
SUPPORTED_LANGUAGES = {"ru", "ro", "en"}

LANGUAGE_ALIASES = {
    "ru": "ru",
    "russian": "ru",
    "ro": "ro",
    "romanian": "ro",
    "en": "en",
    "english": "en",
}


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str


def _request_transcription(
    file_path: str | Path,
    language: str | None,
    response_format: str,
) -> tuple[str, object]:
    if language is not None and language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language")

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError("Audio file is empty")

    client = Groq(api_key=settings.groq_api_key)

    with path.open("rb") as audio:
        options = {
            "file": audio,
            "model": WHISPER_MODEL,
            "response_format": response_format,
        }

        if language is not None:
            options["language"] = language

        result = client.audio.transcriptions.create(**options)

    text = getattr(result, "text", None)

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Transcription is empty")

    return text.strip(), result


def _normalize_detected_language(language: object) -> str:
    if not isinstance(language, str) or not language.strip():
        raise ValueError("Detected language is missing")

    normalized = language.strip().casefold()
    normalized = normalized.replace("_", "-")

    if normalized in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[normalized]

    base_language = normalized.split("-", maxsplit=1)[0]

    if base_language in SUPPORTED_LANGUAGES:
        return base_language

    raise ValueError("Unsupported detected language")


def transcribe_audio(
    file_path: str | Path,
    language: str | None = None,
) -> str:
    """Transcribe audio and return text (legacy interface)."""
    text, _ = _request_transcription(
        file_path,
        language,
        response_format="json",
    )
    return text


def transcribe_audio_with_language(
    file_path: str | Path,
    language: str | None = "auto",
) -> TranscriptionResult:
    """Transcribe audio and return its text and resolved language."""
    if language not in {None, "auto", *SUPPORTED_LANGUAGES}:
        raise ValueError("Unsupported language")

    requested_language = None if language in {None, "auto"} else language

    text, response = _request_transcription(
        file_path,
        requested_language,
        response_format="verbose_json",
    )

    if requested_language is not None:
        resolved_language = requested_language
    else:
        detected_language = getattr(response, "language", None)
        resolved_language = _normalize_detected_language(detected_language)

    return TranscriptionResult(
        text=text,
        language=resolved_language,
    )
