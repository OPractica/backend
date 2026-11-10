from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import Booking, Seat


class BookingError(Exception):
    # Booking rule violated
    pass


class BookingRuleError(BookingError):
    # Booking doesn’t make sense: past, out of service, too long. API will return 422
    pass


def _overlap_conditions(starts_at: datetime, ends_at: datetime) -> tuple:
    return (
        Booking.status == "confirmed",
        Booking.starts_at < ends_at,
        Booking.ends_at > starts_at,
    )


def validate_booking_rules(starts_at: datetime, ends_at: datetime) -> None:
    office_tz = ZoneInfo(settings.office_timezone)
    start = starts_at.astimezone(office_tz)
    end = ends_at.astimezone(office_tz)

    if end <= start:
        raise BookingRuleError("Время окончания должно быть позже времени начала.")

    now_with_buffer = datetime.now(office_tz) - timedelta(minutes=2)
    if start < now_with_buffer:
        raise BookingRuleError("Нельзя бронировать задним числом.")

    if start.date() != end.date():
        raise BookingRuleError("Бронь должна начинаться и заканчиваться в один день.")

    if start.weekday() >= 5:
        raise BookingRuleError("Офис закрыт по выходным.")

    opens = start.replace(
        hour=settings.office_open_hour, minute=0, second=0, microsecond=0
    )
    closes = start.replace(
        hour=settings.office_close_hour, minute=0, second=0, microsecond=0
    )
    if start < opens or end > closes:
        raise BookingRuleError(
            f"Часы работы офиса: с {settings.office_open_hour:02d}:00 до {settings.office_close_hour:02d}:00."
        )

    if end - start > timedelta(hours=settings.booking_max_hours):
        raise BookingRuleError(
            f"Длительность брони не может превышать {settings.booking_max_hours} часов."
        )

    if end - start < timedelta(minutes=settings.booking_min_minutes):
        raise BookingRuleError(
            f"Минимальная длительность брони — {settings.booking_min_minutes} минут."
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


async def get_seats_availability(
    session: AsyncSession,
    starts_at: datetime,
    ends_at: datetime,
):
    is_booked = exists().where(
        Booking.seat_id == Seat.id,
        *_overlap_conditions(starts_at, ends_at),
    )
    stmt = (
        select(Seat.id, Seat.label, is_booked.label("is_booked"))
        .where(Seat.is_active.is_(True))
        .order_by(Seat.id)
    )
    result = await session.execute(stmt)
    return result.all()


async def check_user(
    session: AsyncSession,
    user_id: int,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    # Checks if the user already has another active booking for that time
    user_conflict = await session.execute(
        select(Booking.id)
        .where(
            Booking.user_id == user_id,
            *_overlap_conditions(starts_at, ends_at),
        )
        .limit(1)
    )

    if user_conflict.scalar_one_or_none() is not None:
        raise BookingRuleError("У вас уже есть активная бронь на это время.")


async def create_booking(
    session: AsyncSession,
    user_id: int,
    seat_id: int,
    starts_at: datetime,
    ends_at: datetime,
    source: str = "manual",
) -> Booking:

    validate_booking_rules(starts_at, ends_at)
    await check_user(session, user_id, starts_at, ends_at)

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
