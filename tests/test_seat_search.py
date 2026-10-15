import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.rag.search import search_seats


class FakeSession:
    def __init__(self, seats):
        self.seats = seats

    async def scalars(self, statement):
        result = MagicMock()
        result.all.return_value = self.seats
        return result


def make_seat(
    seat_id=1,
    near_window=True,
    quiet=True,
    monitors=2,
    active=True,
):
    return SimpleNamespace(
        id=seat_id,
        label=f"A-{seat_id:02}",
        floor=7,
        zone="A",
        is_active=active,
        attributes={
            "near_window": near_window,
            "quiet": quiet,
            "monitors": monitors,
            "docking_station": True,
        },
    )


RU_TEXT = (
    "\u0425\u043e\u0447\u0443 "
    "\u0442\u0438\u0445\u043e\u0435 "
    "\u043c\u0435\u0441\u0442\u043e "
    "\u0432\u043e\u0437\u043b\u0435 "
    "\u043e\u043a\u043d\u0430 "
    "\u0441 \u0434\u0432\u0443\u043c\u044f "
    "\u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0430\u043c\u0438"
)


def run_search(text, seats, language="ru"):
    return asyncio.run(
        search_seats(
            text=text,
            language=language,
            session=FakeSession(seats),
            mode="database",
        )
    )


def test_database_search_finds_matching_seat():
    result = run_search(
        RU_TEXT,
        [
            make_seat(seat_id=1),
            make_seat(seat_id=2, near_window=False),
            make_seat(seat_id=3, monitors=1),
        ],
    )

    assert result["total"] == 1
    assert result["matches"][0]["id"] == 1
    assert result["data_source"] == "database"
    assert result["availability_checked"] is False
    assert result["booking_created"] is False


def test_database_search_returns_empty_result():
    result = run_search(RU_TEXT, [])

    assert result["matches"] == []
    assert result["total"] == 0
    assert result["data_source"] == "database"


def test_database_search_excludes_inactive_seats():
    result = run_search(
        RU_TEXT,
        [make_seat(active=False)],
    )

    assert result["total"] == 0


def test_database_search_excludes_wrong_attributes():
    result = run_search(
        RU_TEXT,
        [
            make_seat(seat_id=1, quiet=False),
            make_seat(seat_id=2, near_window=False),
            make_seat(seat_id=3, monitors=1),
        ],
    )

    assert result["total"] == 0


def test_demo_search():
    result = asyncio.run(search_seats(RU_TEXT, mode="demo"))

    assert result["data_source"] == "demo"
    assert result["total"] == 1
    assert result["availability_checked"] is False


@pytest.mark.parametrize("language", ["ru", "ro", "en"])
def test_languages_are_supported(language):
    result = run_search(
        "desk",
        [make_seat()],
        language=language,
    )

    assert result["language"] == language
    assert result["total"] == 1


def test_missing_database_session_raises_error():
    with pytest.raises(ValueError, match="AsyncSession"):
        asyncio.run(search_seats(RU_TEXT, mode="database"))


def test_invalid_mode_raises_error():
    with pytest.raises(ValueError, match="Unsupported search mode"):
        asyncio.run(
            search_seats(
                RU_TEXT,
                session=FakeSession([]),
                mode="invalid",
            )
        )


def test_team_booking_seat_attributes():
    seat = {
        "id": 3,
        "label": "7-A03",
        "floor": 7,
        "zone": "window",
        "is_active": True,
        "attributes": {
            "window": True,
            "quiet": True,
            "monitors": 2,
            "dock": False,
        },
    }

    from app.services.rag.search import matches_preferences

    preferences = {
        "near_window": True,
        "quiet": True,
        "monitors_min": 2,
    }

    assert matches_preferences(seat, preferences) is True
