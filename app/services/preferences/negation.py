import re

NEGATIVE_PATTERNS = {
    "ru": {
        "near_window": [
            r"\bне хочу\b[^.!?;,\n]{0,60}\b(?:у|возле|около)\s+(?:самого\s+)?(?:окна|окошка)\b",
            r"\bне хочу\b[^.!?;,\n]{0,60}\bрядом с окном\b",
            r"\bне\s+(?:у|возле|около)\s+(?:окна|окошка)\b",
            r"\bподальше от окна\b",
        ],
        "quiet": [
            r"\bне хочу\b[^.!?;,\n]{0,60}\bтихое место\b",
            r"\bне хочу\b[^.!?;,\n]{0,60}\bтихую зону\b",
        ],
    },
    "ro": {
        "near_window": [
            r"\bnu vreau\b[^.!?;,\n]{0,60}\b(?:l[âa]ng[ăa]|aproape de)\s+(?:geam|fereastr[ăa])\b",
            r"\bnu\s+(?:l[âa]ng[ăa]|aproape de)\s+(?:geam|fereastr[ăa])\b",
        ],
        "quiet": [
            r"\bnu vreau\b[^.!?;,\n]{0,60}\b(?:loc|birou|zon[ăa])\s+lini[șşs]tit[ăa]?\b",
        ],
    },
    "en": {
        "near_window": [
            r"\b(?:don't|don’t|do not)\s+want\b[^.!?;,\n]{0,60}\b(?:near|by|next to|beside)\s+(?:the\s+|a\s+)?window\b",
            r"\b(?:don't|don’t|do not)\s+want\b[^.!?;,\n]{0,60}\bwindow\s+(?:seat|desk)\b",
            r"\bnot\s+(?:near|by|next to|beside)\s+(?:the\s+|a\s+)?window\b",
            r"\baway from\s+(?:the\s+|a\s+)?window\b",
        ],
        "quiet": [
            r"\b(?:don't|don’t|do not)\s+want\b[^.!?;,\n]{0,60}\bquiet\s+(?:place|desk|area|zone)\b",
        ],
    },
}

OPTIONAL_PATTERNS = {
    "ru": {
        "quiet": [
            r"\bне обязательно\b[^.!?;,\n]{0,40}\bтихое место\b",
            r"\bне нужно\b[^.!?;,\n]{0,40}\bтихое место\b",
        ],
    },
    "ro": {
        "quiet": [
            r"\bnu neap[ăa]rat\b[^.!?;,\n]{0,40}\bloc lini[șşs]tit\b",
        ],
    },
    "en": {
        "quiet": [
            r"\bnot necessarily\s+(?:a\s+)?quiet\s+(?:place|desk|area)\b",
            r"\bno need for\s+(?:a\s+)?quiet\s+(?:place|desk|area)\b",
        ],
    },
}


def detect_negative_preferences(
    normalized_text: str,
    language: str,
) -> dict[str, bool | None]:
    """Detect rejected and optional seat preferences."""

    result: dict[str, bool | None] = {}

    for attribute, patterns in OPTIONAL_PATTERNS.get(language, {}).items():
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            result[attribute] = None

    for attribute, patterns in NEGATIVE_PATTERNS.get(language, {}).items():
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            result[attribute] = False

    return result
