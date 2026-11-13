import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Seat
from app.services.booking import BookingError, get_seat_by_label

pytestmark = pytest.mark.anyio


async def add_seat(
    session: AsyncSession, label: str, floor: int = 7, is_active: bool = True
) -> Seat:
    seat = Seat(
        label=label, floor=floor, zone="window", attributes={}, is_active=is_active
    )
    session.add(seat)
    await session.flush()
    return seat


async def test_finds_a_seat_by_label_ignoring_case_and_spaces(session: AsyncSession):
    seat = await add_seat(session, "7-A01")

    found = await get_seat_by_label(session, "  7-a01 ")

    assert found.id == seat.id


async def test_unknown_label_raises_a_clear_error(session: AsyncSession):
    with pytest.raises(BookingError, match="не найдено"):
        await get_seat_by_label(session, "NO-SUCH")


async def test_inactive_seat_is_not_found(session: AsyncSession):
    await add_seat(session, "7-A02", is_active=False)

    with pytest.raises(BookingError, match="не найдено"):
        await get_seat_by_label(session, "7-A02")


async def test_label_shared_by_two_seats_is_ambiguous(session: AsyncSession):
    await add_seat(session, "A-01", floor=6)
    await add_seat(session, "A-01", floor=7)

    with pytest.raises(BookingError, match="нескольким"):
        await get_seat_by_label(session, "A-01")
