import unicodedata
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import MeetingRoom, MeetingRoomBooking
from app.services.booking import BookingError, validate_booking_rules


async def get_rooms_with_status(
    session: AsyncSession, office_id: int, starts_at: datetime, ends_at: datetime
) -> list[tuple[MeetingRoom, bool]]:
    is_busy = exists().where(
        MeetingRoomBooking.room_id == MeetingRoom.id,
        MeetingRoomBooking.status == "confirmed",
        MeetingRoomBooking.starts_at < ends_at,
        MeetingRoomBooking.ends_at > starts_at,
    )
    result = await session.execute(
        select(MeetingRoom, is_busy)
        .where(MeetingRoom.office_id == office_id, MeetingRoom.is_active.is_(True))
        .order_by(MeetingRoom.id)
    )
    return [(room, is_busy) for room, is_busy in result]


def _normalize_name(value: str) -> str:
    """'Cabină 1' и 'cabina 1' это одно и то же: регистр, диакритика и пробелы не важны."""
    decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
    return " ".join(
        "".join(ch for ch in decomposed if not unicodedata.combining(ch)).split()
    )


async def get_room_by_alias(
    session: AsyncSession, alias: str, office_id: int
) -> MeetingRoom:
    """Найти активную переговорную офиса по названию (например «Sala 2»)."""
    result = await session.scalars(
        select(MeetingRoom).where(
            MeetingRoom.office_id == office_id, MeetingRoom.is_active.is_(True)
        )
    )
    wanted = _normalize_name(alias)
    rooms = [room for room in result if _normalize_name(room.alias) == wanted]
    if not rooms:
        raise BookingError(f"Переговорка {alias} не найдена.", "room_not_found")
    if len(rooms) > 1:
        raise BookingError(
            f"Название {alias} подходит нескольким переговорным.",
            "room_alias_ambiguous",
        )
    return rooms[0]


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

    booking = MeetingRoomBooking(
        user_id=user_id, room_id=room_id, starts_at=starts_at, ends_at=ends_at
    )
    try:
        # The database constraint rejects an overlapping booking, even a parallel
        # one. The savepoint keeps the session usable after that
        async with session.begin_nested():
            session.add(booking)
    except IntegrityError as err:
        if "excl_meeting_room_bookings_no_overlap" not in str(err.orig):
            raise
        raise BookingError(
            f"Переговорка {room.alias} уже занята на это время.", "room_already_booked"
        ) from None
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
    result = await session.scalars(
        select(MeetingRoomBooking)
        .where(
            MeetingRoomBooking.user_id == user_id,
            MeetingRoomBooking.status == "confirmed",
            MeetingRoomBooking.ends_at > datetime.now(UTC),
        )
        .order_by(MeetingRoomBooking.starts_at)
    )
    return list(result)
