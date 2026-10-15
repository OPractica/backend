from pathlib import Path

from groq import Groq

from app.core.config import settings

MODEL = "whisper-large-v3-turbo"


def transcribe_audio(
    file_path: str | Path,
    language: str | None = None,
) -> str:
    """Распознаёт аудио через Groq Whisper."""

    if language not in ("ru", "ro", "en", None):
        raise ValueError("Unsupported language")

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    client = Groq(api_key=settings.groq_api_key)

    with path.open("rb") as audio:
        options = {
            "file": audio,
            "model": MODEL,
            "response_format": "json",
        }

        if language:
            options["language"] = language

        result = client.audio.transcriptions.create(**options)

    return result.text
