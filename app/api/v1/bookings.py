from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db import get_db
from app.models import User
from app.schemas import BookingIn, BookingOut
from app.services import bookings as svc
from app.services import mail

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _notify(user: User) -> bool:
    return (user.settings or {}).get("notify", True)


@router.post("", response_model=BookingOut, status_code=201)
async def create_booking(
    data: BookingIn, bg: BackgroundTasks, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    b, seat = await svc.create(db, user, data.seat_id, data.date, data.start, data.end)
    if _notify(user):
        bg.add_task(mail.send_mail, user.email, *mail.booking_email(user.full_name, seat.label, b.starts_at, b.ends_at))
    return svc.to_out(b, seat.label)


@router.get("/me", response_model=list[BookingOut])
async def my_bookings(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.upcoming(db, user)


@router.patch("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: str, bg: BackgroundTasks, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    b, seat = await svc.cancel(db, user, booking_id)
    if _notify(user):
        bg.add_task(
            mail.send_mail,
            user.email,
            *mail.booking_email(user.full_name, seat.label, b.starts_at, b.ends_at, cancelled=True),
        )
    return svc.to_out(b, seat.label)
