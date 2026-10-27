from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Booking, Seat, User

pytestmark = pytest.mark.anyio

URL = "/api/v1/seats/availability"
PARAMS = {"starts_at": "2030-01-15T09:00:00Z", "ends_at": "2030-01-15T10:00:00Z"}


async def add_seat(session: AsyncSession, label: str, is_active: bool = True) -> Seat:
    seat = Seat(label=label, floor=7, zone="window", is_active=is_active)
    session.add(seat)
    await session.flush()
    return seat


async def add_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Test User")
    session.add(user)
    await session.flush()
    return user


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


async def statuses(client: AsyncClient, params: dict = PARAMS) -> dict[str, str]:
    response = await client.get(URL, params=params)
    assert response.status_code == 200
    return {seat["label"]: seat["status"] for seat in response.json()}


async def test_invalid_time_interval_returns_422(client: AsyncClient):
    response = await client.get(
        URL,
        params={
            "starts_at": "2030-01-15T10:00:00Z",
            "ends_at": "2030-01-15T09:00:00Z",
        },
    )
    assert response.status_code == 422


async def test_seat_without_bookings_is_free(
    client: AsyncClient, session: AsyncSession
):
    await add_seat(session, "T-1")

    assert await statuses(client) == {"T-1": "free"}


async def test_overlapping_confirmed_booking_marks_seat_booked(
    client: AsyncClient, session: AsyncSession
):
    user = await add_user(session, "a@example.com")
    seat = await add_seat(session, "T-1")
    await add_seat(session, "T-2")
    await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 9, 30, tzinfo=UTC),
        datetime(2030, 1, 15, 10, 30, tzinfo=UTC),
    )

    assert await statuses(client) == {"T-1": "booked", "T-2": "free"}


async def test_cancelled_booking_does_not_block_seat(
    client: AsyncClient, session: AsyncSession
):
    user = await add_user(session, "a@example.com")
    seat = await add_seat(session, "T-1")
    booking = await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 9, tzinfo=UTC),
        datetime(2030, 1, 15, 10, tzinfo=UTC),
    )
    booking.status = "cancelled"
    await session.flush()

    assert await statuses(client) == {"T-1": "free"}


async def test_adjacent_booking_does_not_block_seat(
    client: AsyncClient, session: AsyncSession
):
    user = await add_user(session, "a@example.com")
    seat = await add_seat(session, "T-1")
    # Бронь с 08:00 до 09:00, а интервал запроса — с 09:00 до 10:00
    await add_booking(
        session,
        user,
        seat,
        datetime(2030, 1, 15, 8, tzinfo=UTC),
        datetime(2030, 1, 15, 9, tzinfo=UTC),
    )

    assert await statuses(client) == {"T-1": "free"}
