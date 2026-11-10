import re

NEGATIVE_PATTERNS = {
    "ru": {
        "near_window": [
            r"\bне хочу\b[^.!?;,\n]{0,60}\b(?:у|возле|около)\s+(?:самого\s+|большого\s+)?(?:окна|окошка)\b",
            r"\bне хочу\b[^.!?;,\n]{0,60}\bрядом с (?:окном|окнами|окошком)\b",
            r"\bне\s+(?:у|возле|около)\s+(?:самого\s+)?(?:окна|окошка)\b",
            r"\bподальше от окна\b",
        ],
        "quiet": [
            r"\bне хочу\b[^.!?;,\n]{0,60}\b(?:тихое(?:\s+рабочее)?\s+место|тихую зону|тихий стол|спокойное место)\b",
        ],
        "two_monitors": [
            r"\b(?:не хочу|не нужны|не нужно)\b[^.!?;,\n]{0,60}\b(?:два|двумя|2)\s+(?:монитор(?:а|ами)|экран(?:а|ами)|диспле(?:я|ями))\b",
            r"\b(?:не хочу|не нужны|не нужно)\b[^.!?;,\n]{0,60}\b(?:пару|пара|парой)\s+мониторов\b",
        ],
        "docking_station": [
            r"\b(?:не хочу|не нужна|не нужен|не нужно)\b[^.!?;,\n]{0,60}\b(?:док[- ]?станци(?:я|и|ю|ей)|док для ноутбука)\b",
        ],
    },
    "ro": {
        "near_window": [
            r"\bnu vreau\b[^.!?;,\n]{0,60}\b(?:l[âa]ng[ăa]|aproape de|la)\s+(?:(?:o|un)\s+)?(?:geam|fereastr[ăa])\b",
            r"\bnu\s+(?:l[âa]ng[ăa]|aproape de|la)\s+(?:(?:o|un)\s+)?(?:geam|fereastr[ăa])\b",
        ],
        "quiet": [
            r"\bnu vreau\b[^.!?;,\n]{0,60}\b(?:loc|birou|zon[ăa])\s+lini[șşs]tit[ăa]?\b",
        ],
        "two_monitors": [
            r"\bnu (?:vreau|am nevoie de)\b[^.!?;,\n]{0,60}\b(?:dou[ăa]|2)\s+(?:monitoare|ecrane|display-uri)\b",
        ],
        "docking_station": [
            r"\bnu (?:vreau|am nevoie de)\b[^.!?;,\n]{0,60}\b(?:sta[țţt]ie de andocare|docking station|dock pentru laptop)\b",
        ],
    },
    "en": {
        "near_window": [
            r"\b(?:don't|don’t|do not)\s+(?:want|need)\b[^.!?;,\n]{0,60}\b(?:near|by|close to|next to|beside)\s+(?:the\s+|a\s+)?windows?\b",
            r"\b(?:don't|don’t|do not)\s+(?:want|need)\b[^.!?;,\n]{0,60}\bwindow\s+(?:seat|desk)\b",
            r"\bnot\s+(?:near|by|close to|next to|beside)\s+(?:the\s+|a\s+)?windows?\b",
            r"\baway from\s+(?:the\s+|a\s+)?windows?\b",
        ],
        "quiet": [
            r"\b(?:don't|don’t|do not)\s+(?:want|need)\b[^.!?;,\n]{0,60}\bquiet\s+(?:place|desk|area|zone|workspace)\b",
        ],
        "two_monitors": [
            r"\b(?:don't|don’t|do not)\s+(?:want|need)\b[^.!?;,\n]{0,60}\b(?:two|2|dual)\s+(?:monitors|screens|displays?)\b",
        ],
        "docking_station": [
            r"\b(?:don't|don’t|do not)\s+(?:want|need)\b[^.!?;,\n]{0,60}\b(?:a\s+)?(?:docking station|laptop dock|usb[- ]c dock)\b",
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
    """Detect explicitly rejected and optional seat preferences.

    Args:
        normalized_text: Text normalized by parser.normalize().
        language: One of "ru", "ro", or "en".

    Returns:
        Mapping of preference names to:
        - False: explicitly rejected preference.
        - None: optional preference, not a strict requirement.
    """
    result: dict[str, bool | None] = {}

    for attribute, patterns in OPTIONAL_PATTERNS.get(language, {}).items():
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            result[attribute] = None

    for attribute, patterns in NEGATIVE_PATTERNS.get(language, {}).items():
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            result[attribute] = False

    return result
