import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MODEL = "whisper-large-v3-turbo"


def transcribe_audio(
    file_path: str,
    language: str | None = None,
) -> str:

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY не найден в .env")

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if language not in ("ru", "ro", "en", None):
        raise ValueError("Неподдерживаемый язык")

    client = Groq(api_key=api_key)

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
