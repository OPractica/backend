from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import tools as ai_tools
from app.ai.tools import make_tools
from app.models.database import Booking, Seat, User

pytestmark = pytest.mark.anyio

# A winter date far in the future: the office time zone is UTC+2 (no daylight saving)
START = "2030-01-15T09:00"
END = "2030-01-15T10:00"


async def add_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Test User")
    session.add(user)
    await session.flush()
    return user


async def add_seat(session: AsyncSession, label: str, zone: str) -> Seat:
    seat = Seat(label=label, floor=7, zone=zone, attributes={"quiet": zone == "quiet"})
    session.add(seat)
    await session.flush()
    return seat


async def add_booking(
    session: AsyncSession,
    user: User,
    seat: Seat,
    starts_at: datetime,
    ends_at: datetime,
) -> Booking:
    booking = Booking(
        user_id=user.id, seat_id=seat.id, starts_at=starts_at, ends_at=ends_at
    )
    session.add(booking)
    await session.flush()
    return booking


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await add_user(session, "me@example.com")


@pytest.fixture
async def tools(monkeypatch, session: AsyncSession, user: User) -> dict:
    # The tools open their own database session. In tests we give them the test
    # session instead, so everything stays inside the rolled-back transaction.
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)
    return {tool.name: tool for tool in make_tools(user.id)}


def test_tool_cards_have_expected_names_and_arguments():
    cards = {tool.name: list(tool.args) for tool in make_tools(1)}

    assert cards == {
        "search_free_seats": ["start", "end", "zone"],
        "book_seat": ["seat", "start", "end"],
        "cancel_my_booking": ["booking_id"],
        "list_my_bookings": [],
    }


async def test_search_lists_free_seats(tools: dict, session: AsyncSession):
    await add_seat(session, "T-1", "window")
    await add_seat(session, "T-2", "quiet")

    result = await tools["search_free_seats"].ainvoke({"start": START, "end": END})

    assert "seat=T-1 zone=window" in result
    assert "seat=T-2 zone=quiet" in result


async def test_search_filters_by_zone(tools: dict, session: AsyncSession):
    await add_seat(session, "T-1", "window")
    await add_seat(session, "T-2", "quiet")

    result = await tools["search_free_seats"].ainvoke(
        {"start": START, "end": END, "zone": "quiet"}
    )

    assert "T-2" in result
    assert "T-1" not in result


async def test_search_says_when_no_seats(tools: dict):
    result = await tools["search_free_seats"].ainvoke({"start": START, "end": END})

    assert result == "no free seats for this time"


async def test_search_skips_booked_seat(tools: dict, session: AsyncSession, user: User):
    booked = await add_seat(session, "T-1", "window")
    await add_seat(session, "T-2", "window")
    # 07:00-08:00 UTC is 09:00-10:00 in the office
    await add_booking(
        session,
        user,
        booked,
        datetime(2030, 1, 15, 7, tzinfo=UTC),
        datetime(2030, 1, 15, 8, tzinfo=UTC),
    )

    result = await tools["search_free_seats"].ainvoke({"start": START, "end": END})

    assert "T-1" not in result
    assert "T-2" in result


async def test_search_times_are_office_local_not_utc(
    tools: dict, session: AsyncSession, user: User
):
    seat = await add_seat(session, "T-1", "window")
    # 09:00-10:00 UTC is 11:00-12:00 in the office, so 09:00-10:00 office time is free
    await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 9, tzinfo=UTC),
        datetime(2030, 1, 15, 10, tzinfo=UTC),
    )

    result = await tools["search_free_seats"].ainvoke({"start": START, "end": END})

    assert "T-1" in result


async def test_search_with_unreadable_time_returns_error_text(tools: dict):
    result = await tools["search_free_seats"].ainvoke({"start": "завтра", "end": END})

    assert result.startswith("error invalid_time_format")


async def test_search_with_end_before_start_returns_error_text(
    tools: dict, session: AsyncSession
):
    await add_seat(session, "T-1", "window")

    result = await tools["search_free_seats"].ainvoke({"start": END, "end": START})

    assert result.startswith("error invalid_time_range")
    assert "T-1" not in result


async def test_list_my_bookings_when_empty(tools: dict):
    result = await tools["list_my_bookings"].ainvoke({})

    assert result == "the user has no active bookings"


async def test_list_my_bookings_shows_only_own_bookings(
    tools: dict, session: AsyncSession, user: User
):
    seat = await add_seat(session, "T-1", "window")
    other = await add_user(session, "other@example.com")
    mine = await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 7, tzinfo=UTC),
        datetime(2030, 1, 15, 8, tzinfo=UTC),
    )
    theirs = await add_booking(
        session,
        other,
        seat,
        datetime(2030, 1, 15, 12, tzinfo=UTC),
        datetime(2030, 1, 15, 13, tzinfo=UTC),
    )

    result = await tools["list_my_bookings"].ainvoke({})

    assert f"booking {mine.id}: seat T-1" in result
    assert "2030-01-15 09:00 - 2030-01-15 10:00" in result
    assert f"booking {theirs.id}:" not in result


async def test_book_seat_creates_booking_for_current_user(
    tools: dict, session: AsyncSession, user: User
):
    seat = await add_seat(session, "T-1", "window")

    result = await tools["book_seat"].ainvoke(
        {"seat": seat.label, "start": START, "end": END}
    )

    booking = await session.scalar(select(Booking).where(Booking.seat_id == seat.id))
    assert booking is not None
    assert booking.user_id == user.id
    assert booking.source == "ai"
    assert booking.status == "confirmed"
    # 09:00 in the office is 07:00 UTC
    assert booking.starts_at == datetime(2030, 1, 15, 7, tzinfo=UTC)
    assert result.startswith("booking created")
    assert f"booking id {booking.id}" in result
    assert "from 2030-01-15 09:00 to 2030-01-15 10:00" in result


async def test_book_seat_rejects_overlapping_booking(
    tools: dict, session: AsyncSession
):
    seat = await add_seat(session, "T-1", "window")
    other = await add_user(session, "other@example.com")
    await add_booking(
        session,
        other,
        seat,
        datetime(2030, 1, 15, 7, tzinfo=UTC),
        datetime(2030, 1, 15, 8, tzinfo=UTC),
    )

    result = await tools["book_seat"].ainvoke(
        {"seat": seat.label, "start": START, "end": END}
    )

    bookings = (
        await session.scalars(select(Booking).where(Booking.seat_id == seat.id))
    ).all()
    assert result.startswith("error seat_already_booked")
    assert len(bookings) == 1


async def test_book_seat_with_unknown_seat_returns_error_text(tools: dict):
    result = await tools["book_seat"].ainvoke(
        {"seat": "NO-SUCH", "start": START, "end": END}
    )

    assert result.startswith("error seat_not_found")


async def test_book_seat_with_unreadable_time_creates_nothing(
    tools: dict, session: AsyncSession
):
    seat = await add_seat(session, "T-1", "window")

    result = await tools["book_seat"].ainvoke(
        {"seat": seat.label, "start": "завтра", "end": END}
    )

    bookings = (await session.scalars(select(Booking))).all()
    assert result.startswith("error invalid_time_format")
    assert bookings == []


async def test_cancel_own_booking(tools: dict, session: AsyncSession, user: User):
    seat = await add_seat(session, "T-1", "window")
    booking = await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 7, tzinfo=UTC),
        datetime(2030, 1, 15, 8, tzinfo=UTC),
    )

    result = await tools["cancel_my_booking"].ainvoke({"booking_id": booking.id})

    assert result == f"booking {booking.id} cancelled"
    assert booking.status == "cancelled"


async def test_cancel_foreign_booking_is_rejected(tools: dict, session: AsyncSession):
    seat = await add_seat(session, "T-1", "window")
    other = await add_user(session, "other@example.com")
    booking = await add_booking(
        session,
        other,
        seat,
        datetime(2030, 1, 15, 7, tzinfo=UTC),
        datetime(2030, 1, 15, 8, tzinfo=UTC),
    )

    result = await tools["cancel_my_booking"].ainvoke({"booking_id": booking.id})

    assert result.startswith("error booking_not_found")
    assert booking.status == "confirmed"


async def test_cancel_unknown_booking_returns_error_text(tools: dict):
    result = await tools["cancel_my_booking"].ainvoke({"booking_id": 999999})

    assert result.startswith("error booking_not_found")


async def test_booked_seat_becomes_free_again_after_cancel(
    tools: dict, session: AsyncSession
):
    seat = await add_seat(session, "T-1", "window")
    window = {"start": START, "end": END}

    booked = await tools["book_seat"].ainvoke({"seat": seat.label, **window})
    during = await tools["search_free_seats"].ainvoke(window)
    booking = await session.scalar(select(Booking).where(Booking.seat_id == seat.id))
    await tools["cancel_my_booking"].ainvoke({"booking_id": booking.id})
    after = await tools["search_free_seats"].ainvoke(window)

    assert booked.startswith("booking created")
    assert during == "no free seats for this time"
    assert "T-1" in after
