from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import MeetingRoom, MeetingRoomBooking
from app.services.booking import BookingError, validate_booking_rules


def _room_is_busy(starts_at: datetime, ends_at: datetime):
    return exists().where(
        MeetingRoomBooking.room_id == MeetingRoom.id,
        MeetingRoomBooking.status == "confirmed",
        MeetingRoomBooking.starts_at < ends_at,
        MeetingRoomBooking.ends_at > starts_at,
    )


async def get_rooms_with_status(
    session: AsyncSession, office_id: int, starts_at: datetime, ends_at: datetime
) -> list[tuple[MeetingRoom, bool]]:
    stmt = (
        select(MeetingRoom, _room_is_busy(starts_at, ends_at).label("is_busy"))
        .where(MeetingRoom.office_id == office_id, MeetingRoom.is_active.is_(True))
        .order_by(MeetingRoom.id)
    )
    result = await session.execute(stmt)
    return [(room, is_busy) for room, is_busy in result.all()]


async def get_busy_room_ids(
    session: AsyncSession, office_id: int, starts_at: datetime, ends_at: datetime
) -> list[int]:
    stmt = (
        select(MeetingRoom.id)
        .where(
            MeetingRoom.office_id == office_id,
            MeetingRoom.is_active.is_(True),
            _room_is_busy(starts_at, ends_at),
        )
        .order_by(MeetingRoom.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_room_booking(
    session: AsyncSession,
    user_id: int,
    room_id: int,
    starts_at: datetime,
    ends_at: datetime,
) -> MeetingRoomBooking:
    validate_booking_rules(starts_at, ends_at)

    room = await session.get(MeetingRoom, room_id)
    if room is None or not room.is_active:
        raise BookingError(
            f"Переговорка {room_id} не найдена или недоступна.", "room_not_found"
        )

    taken_error = BookingError(
        f"Переговорка {room.alias} уже занята на это время.", "room_already_booked"
    )
    conflict = await session.execute(
        select(MeetingRoomBooking.id)
        .where(
            MeetingRoomBooking.room_id == room_id,
            MeetingRoomBooking.status == "confirmed",
            MeetingRoomBooking.starts_at < ends_at,
            MeetingRoomBooking.ends_at > starts_at,
        )
        .limit(1)
    )
    if conflict.scalar_one_or_none() is not None:
        raise taken_error

    booking = MeetingRoomBooking(
        user_id=user_id, room_id=room_id, starts_at=starts_at, ends_at=ends_at
    )
    try:
        # Savepoint: a parallel booking may slip past the check above,
        # then the database constraint rejects ours and the session stays usable
        async with session.begin_nested():
            session.add(booking)
    except IntegrityError as err:
        if "excl_meeting_room_bookings_no_overlap" not in str(err.orig):
            raise
        raise taken_error from None
    return booking


async def cancel_room_booking(
    session: AsyncSession, user_id: int, booking_id: int
) -> MeetingRoomBooking:
    booking = await session.get(MeetingRoomBooking, booking_id)
    # Same answer for someone else's booking and a missing one
    if booking is None or booking.user_id != user_id:
        raise BookingError(f"Бронь {booking_id} не найдена.", "booking_not_found")
    if booking.status != "confirmed":
        raise BookingError(
            f"Бронь {booking_id} уже отменена.", "booking_already_cancelled"
        )
    booking.status = "cancelled"
    await session.flush()
    return booking


async def list_user_room_bookings(
    session: AsyncSession, user_id: int
) -> list[MeetingRoomBooking]:
    # Like seat bookings: only confirmed ones that have not ended yet
    result = await session.execute(
        select(MeetingRoomBooking)
        .where(
            MeetingRoomBooking.user_id == user_id,
            MeetingRoomBooking.status == "confirmed",
            MeetingRoomBooking.ends_at > datetime.now(UTC),
        )
        .order_by(MeetingRoomBooking.starts_at)
    )
    return list(result.scalars().all())
