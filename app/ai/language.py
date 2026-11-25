"""Определение языка сообщения кодом (ru / ro / en), а не моделью."""

from collections.abc import Iterable
from typing import Literal

Language = Literal["ru", "ro", "en"]
LANGUAGES: tuple[Language, ...] = ("ru", "ro", "en")
LANGUAGE_NAMES: dict[Language, str] = {
    "ru": "русский",
    "ro": "румынский",
    "en": "английский",
}
# Короткая латиница («ok», «da», «yes») не показывает язык: ru/ro/en нельзя отличить
MIN_LATIN_LETTERS = 6

ROMANIAN_DIACRITICS = "ăâîșțşţ"
ROMANIAN_WORDS = frozenset(
    {
        "vreau", "un", "loc", "locul", "locuri", "mâine", "maine", "poimâine", "poimaine",
        "rezervă", "rezerva", "rezervare", "rezervarea", "vă", "rog", "între", "intre",
        "la", "și", "si", "pentru", "orice", "primul", "prima", "anulează", "anuleaza",
        "bună", "buna", "mulțumesc", "multumesc", "salut", "care", "doar", "dă-mi", "arată",
    }
)  # fmt: skip


def detect_language(
    text: str, hint: Language | None = None, default: Language = "ru"
) -> Language:
    """Определить язык сообщения.

    hint главнее всего: например, язык, который уже определило распознавание речи.
    default возвращается, если в тексте нет букв (например, «7» или «7-A03»):
    тогда разговор продолжается на том языке, на котором шёл раньше.
    """
    if hint in LANGUAGES:
        return hint
    # Слова с цифрами (названия мест «7-A03», номера броней) не показывают язык
    words_without_digits = [
        w for w in text.split() if not any(ch.isdigit() for ch in w)
    ]
    letters = [ch for ch in " ".join(words_without_digits) if ch.isalpha()]
    if not letters:
        return default
    cyrillic = sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in letters)
    if cyrillic / len(letters) > 0.5:
        return "ru"
    lowered = " ".join(words_without_digits).lower()
    words = {word.strip(".,:;!?()«»\"'-—") for word in lowered.split()}
    if words & ROMANIAN_WORDS or any(ch in lowered for ch in ROMANIAN_DIACRITICS):
        return "ro"
    return "en"


def detect_confident(text: str) -> Language | None:
    """Язык сообщения или None, если по тексту его нельзя определить уверенно.

    Кириллица и румынские слова или буквы надёжны всегда. Короткая латиница
    («ok», «da», «yes») и сообщения без букв («7-A03», «1») неоднозначны.
    """
    words = [w for w in text.split() if not any(ch.isdigit() for ch in w)]
    letters = [ch for ch in " ".join(words) if ch.isalpha()]
    if not letters:
        return None
    language = detect_language(text)
    if language == "en" and len(letters) < MIN_LATIN_LETTERS:
        return None
    return language


def dialog_language(
    texts_newest_first: Iterable[str],
    hint: Language | None = None,
    default: Language = "ru",
) -> Language:
    """Язык диалога: подсказка клиента, иначе последнее сообщение с понятным языком.

    Короткие ответы вроде «да», «ok», «7-A03» не переключают язык диалога:
    берётся язык ближайшего предыдущего сообщения пользователя.
    """
    if hint in LANGUAGES:
        return hint
    for text in texts_newest_first:
        if (language := detect_confident(text)) is not None:
            return language
    return default
