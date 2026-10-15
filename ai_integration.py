from pathlib import Path

from preferences.parser import extract_preferences
from prompts.loader import get_system_prompt
from rag.context import retrieve_seat_context
from rag.search import search_seats
from voice.transcribe_audio import transcribe_audio


def process_user_text(
    text: str,
    language: str = "ru",
) -> dict:
    """
    Подготавливает текст пользователя для AI-агента.
    Не создаёт бронирование.
    """

    preferences = extract_preferences(text, language)
    search_result = search_seats(text, language)
    context = retrieve_seat_context(text, language)
    system_prompt = get_system_prompt(language)

    return {
        "text": text,
        "language": language,
        "preferences": preferences,
        "seat_candidates": search_result["matches"],
        "context": context,
        "system_prompt": system_prompt,
        "data_source": "demo",
        "availability_checked": False,
    }


def process_user_audio(
    file_path: str | Path,
    language: str = "ru",
) -> dict:
    """
    Преобразует аудио в текст и готовит данные для агента.
    Не создаёт бронирование.
    """

    text = transcribe_audio(str(file_path), language)

    return process_user_text(text, language)
