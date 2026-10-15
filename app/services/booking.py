from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Booking, Seat


class BookingError(Exception):
    """Нарушено правило бронирования. Текст понятен человеку и модели."""


def _overlap_conditions(starts_at: datetime, ends_at: datetime) -> tuple:
    return (
        Booking.status == "confirmed",
        Booking.starts_at < ends_at,
        Booking.ends_at > starts_at,
    )


async def find_free_seats(
    session: AsyncSession,
    starts_at: datetime,
    ends_at: datetime,
    zone: str | None = None,
) -> list[Seat]:
    busy = exists().where(
        Booking.seat_id == Seat.id,
        *_overlap_conditions(starts_at, ends_at),
    )
    stmt = select(Seat).where(Seat.is_active.is_(True), ~busy).order_by(Seat.id)
    if zone:
        stmt = stmt.where(Seat.zone == zone)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_booking(
    session: AsyncSession,
    user_id: int,
    seat_id: int,
    starts_at: datetime,
    ends_at: datetime,
    source: str = "manual",
) -> Booking:
    if ends_at <= starts_at:
        raise BookingError("Время окончания должно быть позже времени начала.")

    seat = await session.get(Seat, seat_id)
    if seat is None or not seat.is_active:
        raise BookingError(f"Место {seat_id} не найдено или недоступно.")

    conflict = await session.execute(
        select(Booking.id)
        .where(Booking.seat_id == seat_id, *_overlap_conditions(starts_at, ends_at))
        .limit(1)
    )
    if conflict.scalar_one_or_none() is not None:
        raise BookingError(f"Место {seat.label} уже занято на это время.")

    booking = Booking(
        user_id=user_id,
        seat_id=seat_id,
        starts_at=starts_at,
        ends_at=ends_at,
        source=source,
    )
    session.add(booking)
    await session.flush()
    return booking


async def cancel_booking(
    session: AsyncSession, user_id: int, booking_id: int
) -> Booking:
    booking = await session.get(Booking, booking_id)
    # Для чужой и для несуществующей брони ответ одинаковый: не раскрываем чужие данные.
    if booking is None or booking.user_id != user_id:
        raise BookingError(f"Бронь {booking_id} не найдена.")
    if booking.status != "confirmed":
        raise BookingError(f"Бронь {booking_id} уже отменена.")

    booking.status = "cancelled"
    await session.flush()
    return booking


async def list_user_bookings(
    session: AsyncSession, user_id: int, include_past: bool = False
) -> list[Booking]:
    stmt = select(Booking).where(
        Booking.user_id == user_id, Booking.status == "confirmed"
    )
    if not include_past:
        stmt = stmt.where(Booking.ends_at > datetime.now(UTC))
    stmt = stmt.order_by(Booking.starts_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())
