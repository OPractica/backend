import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services.rag.availability import find_matching_available_seats

TEXT = (
    "\u0425\u043e\u0447\u0443 "
    "\u0442\u0438\u0445\u043e\u0435 "
    "\u043c\u0435\u0441\u0442\u043e "
    "\u0432\u043e\u0437\u043b\u0435 "
    "\u043e\u043a\u043d\u0430 "
    "\u0441 \u0434\u0432\u0443\u043c\u044f "
    "\u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0430\u043c\u0438"
)


def make_seat(seat_id, window, quiet, monitors):
    return SimpleNamespace(
        id=seat_id,
        label=f"7-A{seat_id:02}",
        floor=7,
        zone="window",
        is_active=True,
        attributes={
            "window": window,
            "quiet": quiet,
            "monitors": monitors,
            "dock": False,
        },
    )


def test_available_seats_are_filtered_by_preferences():
    free = [
        make_seat(1, True, True, 2),
        make_seat(2, True, False, 2),
        make_seat(3, False, True, 2),
    ]

    async def fake_find_free_seats(session, starts_at, ends_at):
        return free

    result = asyncio.run(
        find_matching_available_seats(
            session=None,
            starts_at=datetime(2026, 12, 1, 9, tzinfo=UTC),
            ends_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
            text=TEXT,
            language="ru",
            find_free_seats=fake_find_free_seats,
        )
    )

    assert result["total"] == 1
    assert result["matches"][0]["id"] == 1
    assert result["availability_checked"] is True
    assert result["booking_created"] is False


def test_invalid_time_range_is_rejected():
    async def fake_find_free_seats(session, starts_at, ends_at):
        return []

    with pytest.raises(ValueError, match="End time"):
        asyncio.run(
            find_matching_available_seats(
                session=None,
                starts_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
                ends_at=datetime(2026, 12, 1, 9, tzinfo=UTC),
                text=TEXT,
                language="ru",
                find_free_seats=fake_find_free_seats,
            )
        )
