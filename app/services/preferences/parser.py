import re
import unicodedata

from app.services.preferences.dictionary import (
    AMBIGUOUS_PREFERENCES,
    PREFERENCE_DICTIONARY,
)


def normalize(text: str) -> str:

    text = unicodedata.normalize("NFC", text)

    text = text.casefold()

    return " ".join(text.split())


def contains_phrase(text: str, phrase: str) -> bool:

    pattern = r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)"

    return re.search(pattern, text) is not None


def extract_preferences(text: str, language: str = "ru") -> dict:

    if language not in {"ru", "ro", "en"}:
        raise ValueError("Unsupported language")

    normalized = normalize(text)

    attributes = {}

    needs_clarification = []

    for key, translations in PREFERENCE_DICTIONARY.items():
        phrases = translations.get(language, [])

        if any(contains_phrase(normalized, p) for p in phrases):
            if key == "two_monitors":
                attributes["monitors_min"] = 2

            else:
                attributes[key] = True

    for key, translations in AMBIGUOUS_PREFERENCES.items():
        phrases = translations.get(language, [])

        if any(contains_phrase(normalized, p) for p in phrases):
            needs_clarification.append(key)

    return {
        "language": language,
        "attributes": attributes,
        "needs_clarification": needs_clarification,
    }
