from pathlib import Path

from app.services.preferences.parser import extract_preferences
from app.services.prompts.loader import get_system_prompt
from app.services.rag.context import retrieve_seat_context
from app.services.rag.search import search_seats
from app.services.voice.transcribe import transcribe_audio


def process_user_text(text: str, language: str = "ru") -> dict:
    preferences = extract_preferences(text, language)
    result = search_seats(text, language)

    return {
        "text": text,
        "language": language,
        "preferences": preferences,
        "seat_candidates": result["matches"],
        "context": retrieve_seat_context(text, language),
        "system_prompt": get_system_prompt(language),
        "data_source": "demo",
        "availability_checked": False,
        "booking_created": False,
    }


def process_user_audio(
    file_path: str | Path,
    language: str = "ru",
) -> dict:
    text = transcribe_audio(file_path, language)
    return process_user_text(text, language)
