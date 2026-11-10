import re
import unicodedata

from app.services.preferences.dictionary import (
    AMBIGUOUS_PREFERENCES,
    PREFERENCE_DICTIONARY,
)
from app.services.preferences.negation import detect_negative_preferences

SUPPORTED_LANGUAGES = {"ru", "ro", "en"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.casefold().split())


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = normalize(phrase)
    pattern = rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)"
    return re.search(pattern, normalized_text) is not None


def extract_preferences(text: str, language: str = "ru") -> dict:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language")

    normalized_text = normalize(text)
    attributes: dict[str, bool | int] = {}
    needs_clarification: list[str] = []

    for preference, translations in PREFERENCE_DICTIONARY.items():
        phrases = translations.get(language, [])

        if not any(contains_phrase(normalized_text, phrase) for phrase in phrases):
            continue

        if preference == "two_monitors":
            attributes["monitors_min"] = 2
        else:
            attributes[preference] = True

    negative_preferences = detect_negative_preferences(
        normalized_text,
        language,
    )

    for preference, value in negative_preferences.items():
        if value is None:
            attributes.pop(preference, None)
        else:
            attributes[preference] = value

    for preference, translations in AMBIGUOUS_PREFERENCES.items():
        phrases = translations.get(language, [])

        if any(contains_phrase(normalized_text, phrase) for phrase in phrases):
            needs_clarification.append(preference)

    return {
        "language": language,
        "attributes": attributes,
        "needs_clarification": needs_clarification,
    }
