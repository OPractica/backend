import json
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Seat
from app.services.preferences.parser import extract_preferences

SearchMode = Literal["database", "demo"]

DATA_FILE = Path(__file__).resolve().parent / "sample_seats.json"


def load_demo_seats() -> list[dict]:
    with DATA_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def matches_preferences(seat: dict, requested: dict) -> bool:
    attributes = seat.get("attributes") or {}

    if seat.get("is_active") is False:
        return False

    near_window = attributes.get(
        "near_window",
        attributes.get("window", False),
    )

    docking_station = attributes.get(
        "docking_station",
        attributes.get("dock", False),
    )

    if requested.get("near_window") and not near_window:
        return False

    if requested.get("quiet") and not attributes.get("quiet", False):
        return False

    if requested.get("docking_station") and not docking_station:
        return False

    try:
        monitors = int(attributes.get("monitors") or 0)
    except (TypeError, ValueError):
        monitors = 0

    return monitors >= requested.get("monitors_min", 0)


async def search_seats(
    text: str,
    language: str = "ru",
    session: AsyncSession | None = None,
    mode: SearchMode = "database",
) -> dict:
    preferences = extract_preferences(text, language)
    requested = preferences["attributes"]

    if mode == "database":
        if session is None:
            raise ValueError("Database search requires AsyncSession")

        result = await session.scalars(
            select(Seat).where(Seat.is_active.is_(True)).order_by(Seat.id)
        )
        seats = [
            {
                "id": seat.id,
                "label": seat.label,
                "floor": seat.floor,
                "zone": seat.zone,
                "is_active": seat.is_active,
                "attributes": seat.attributes or {},
            }
            for seat in result.all()
        ]
    elif mode == "demo":
        seats = load_demo_seats()
    else:
        raise ValueError("Unsupported search mode")

    matches = [seat for seat in seats if matches_preferences(seat, requested)]

    return {
        "query": text,
        "language": language,
        "preferences": preferences,
        "matches": matches,
        "total": len(matches),
        "data_source": mode,
        "availability_checked": False,
        "booking_created": False,
    }
