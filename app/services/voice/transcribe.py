from pathlib import Path

from groq import Groq

from app.core.config import settings

WHISPER_MODEL = "whisper-large-v3-turbo"
SUPPORTED_LANGUAGES = {"ru", "ro", "en"}


def transcribe_audio(
    file_path: str | Path,
    language: str | None = None,
) -> str:
    """Transcribe an audio file using Groq Whisper."""

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
            "response_format": "json",
        }

        if language is not None:
            options["language"] = language

        result = client.audio.transcriptions.create(**options)

    transcription = result.text.strip()

    if not transcription:
        raise ValueError("Transcription is empty")

    return transcription
