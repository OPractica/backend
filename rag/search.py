
import json
from pathlib import Path

from preferences.parser import extract_preferences

DATA_FILE = Path(__file__).resolve().parent / "sample_seats.json"


def load_seats() -> list[dict]:
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def search_seats(text: str, language: str = "ru") -> dict:
    preferences = extract_preferences(text, language)
    requested = preferences["attributes"]

    matches = []

    for seat in load_seats():
        attributes = seat.get("attributes", {})

        # All recognized requirements must match.
        if requested.get("near_window") and not attributes.get("near_window"):
            continue

        if requested.get("quiet") and not attributes.get("quiet"):
            continue

        if requested.get("docking_station") and not attributes.get("docking_station"):
            continue

        if attributes.get("monitors", 0) < requested.get("monitors_min", 0):
            continue

        matches.append(seat)

    return {
        "query": text,
        "language": language,
        "preferences": preferences,
        "matches": matches,
        "total": len(matches),
        "data_source": "demo",
    }
