from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Booking, Seat, User
from app.schemas import AvailOut
from app.utils import local_tz, now, utc


def _at(d: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=local_tz()).astimezone(UTC)


def window(d: date, start: str, end: str) -> tuple[datetime, datetime]:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    if not (settings.open_hour * 60 <= sh * 60 + sm < eh * 60 + em <= settings.close_hour * 60):
        raise HTTPException(
            422, f"Bookings are possible between {settings.open_hour:02d}:00 and {settings.close_hour:02d}:00."
        )
    s, e = _at(d, start), _at(d, end)
    if e <= now():
        raise HTTPException(422, "That time has already passed.")
    return s, e


async def availability(db: AsyncSession, d: date, user_id: str | None) -> list[AvailOut]:
    s, e = _at(d, "00:00"), _at(d, "00:00") + timedelta(days=1)
    rows = (
        await db.execute(
            select(Booking.seat_id, Booking.id, Booking.user_id, User.full_name)
            .join(User, User.id == Booking.user_id)
            .where(Booking.status == "confirmed", Booking.starts_at < e, Booking.ends_at > s)
        )
    ).all()
    taken: dict[str, AvailOut] = {}
    for seat_id, bid, uid, name in rows:
        if seat_id in taken and taken[seat_id].status == "mine":
            continue
        taken[seat_id] = AvailOut(
            seat_id=seat_id,
            status="mine" if uid == user_id else "busy",
            booked_by=name,
            booking_id=bid if uid == user_id else None,
        )
    seats = (await db.scalars(select(Seat.id).where(Seat.is_active))).all()
    return [taken.get(i) or AvailOut(seat_id=i, status="free") for i in seats]


async def create(db: AsyncSession, user: User, seat_id: str, d: date, start: str, end: str) -> tuple[Booking, Seat]:
    seat = await db.get(Seat, seat_id)
    if not seat or not seat.is_active:
        raise HTTPException(404, "Seat not found.")
    s, e = window(d, start, end)
    overlap = (Booking.status == "confirmed", Booking.starts_at < e, Booking.ends_at > s)
    if await db.scalar(select(Booking.id).where(Booking.seat_id == seat_id, *overlap).limit(1)):
        raise HTTPException(409, "This seat is already booked for that time.")
    if await db.scalar(select(Booking.id).where(Booking.user_id == user.id, *overlap).limit(1)):
        raise HTTPException(409, "You already have a booking for that time.")
    b = Booking(user_id=user.id, seat_id=seat_id, starts_at=s, ends_at=e)
    db.add(b)
    try:
        await db.commit()  # on PostgreSQL the EXCLUDE constraint stops simultaneous double-booking
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(409, "This seat is already booked for that time.") from err
    return b, seat


def to_out(b: Booking, label: str) -> dict:
    s, e = utc(b.starts_at).astimezone(local_tz()), utc(b.ends_at).astimezone(local_tz())
    return {
        "id": b.id,
        "seat_id": b.seat_id,
        "seat_label": label,
        "date": s.date().isoformat(),
        "start": s.strftime("%H:%M"),
        "end": e.strftime("%H:%M"),
        "status": b.status,
    }


async def upcoming(db: AsyncSession, user: User) -> list[dict]:
    rows = (
        await db.execute(
            select(Booking, Seat.label)
            .join(Seat, Seat.id == Booking.seat_id)
            .where(Booking.user_id == user.id, Booking.status == "confirmed", Booking.ends_at > now())
            .order_by(Booking.starts_at)
        )
    ).all()
    return [to_out(b, label) for b, label in rows]


async def cancel(db: AsyncSession, user: User, booking_id: str) -> tuple[Booking, Seat]:
    b = await db.get(Booking, booking_id)
    if not b or (b.user_id != user.id and user.role not in ("owner", "admin")):
        raise HTTPException(404, "Booking not found.")
    b.status = "cancelled"
    await db.commit()
    return b, await db.get(Seat, b.seat_id)
