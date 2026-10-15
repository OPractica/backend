from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Seat
from app.services.preferences.parser import extract_preferences
from app.services.rag.search import matches_preferences

FreeSeatsFinder = Callable[
    [AsyncSession, datetime, datetime],
    Awaitable[list[Seat]],
]


async def find_matching_available_seats(
    session: AsyncSession,
    starts_at: datetime,
    ends_at: datetime,
    text: str,
    language: str,
    find_free_seats: FreeSeatsFinder,
) -> dict:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise ValueError("Timezone-aware datetimes are required")

    if ends_at <= starts_at:
        raise ValueError("End time must be after start time")

    preferences = extract_preferences(text, language)

    free_seats = await find_free_seats(
        session,
        starts_at,
        ends_at,
    )

    matches = []

    for seat in free_seats:
        data = {
            "id": seat.id,
            "label": seat.label,
            "floor": seat.floor,
            "zone": seat.zone,
            "is_active": seat.is_active,
            "attributes": seat.attributes or {},
        }

        if matches_preferences(data, preferences["attributes"]):
            matches.append(data)

    return {
        "language": language,
        "preferences": preferences,
        "matches": matches,
        "total": len(matches),
        "data_source": "database",
        "availability_checked": True,
        "booking_created": False,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
    }
