import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.models.database import Seat
from app.schemas.schemas import BookingCreate, BookingResponse
from app.services.booking import (
    BookingError,
    cancel_booking,
    create_booking,
    list_user_bookings,
)
from app.services.email import get_email_sender
from app.services.email_templates import booking_cancelled_html, booking_confirmed_html

router = APIRouter(prefix="/bookings", tags=["bookings"])
logger = logging.getLogger(__name__)


async def _send_booking_mail(user_email: str, subject: str, html: str) -> None:
    try:
        sender = get_email_sender()
        await sender.send(to=user_email, subject=subject, html=html)
    except Exception:
        logger.exception("Failed to send booking email to %s", user_email)


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def make_booking(
    booking_in: BookingCreate,
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    try:
        booking = await create_booking(
            session=session,
            user_id=current_user.id,
            seat_id=booking_in.seat_id,
            starts_at=booking_in.starts_at,
            ends_at=booking_in.ends_at,
            source=booking_in.source,
        )
        await session.commit()
    except BookingError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from None

    seat = await session.get(Seat, booking.seat_id)
    seat_label = seat.label if seat else f"#{booking.seat_id}"
    subject, html = booking_confirmed_html(booking, seat_label)

    background_tasks.add_task(_send_booking_mail, current_user.email, subject, html)

    return booking


@router.get("/me", response_model=list[BookingResponse])
async def get_my_bookings(session: SessionDep, current_user: CurrentUser):
    return await list_user_bookings(session=session, user_id=current_user.id)


@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_my_booking(
    booking_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    try:
        booking = await cancel_booking(
            session=session, user_id=current_user.id, booking_id=booking_id
        )
        await session.commit()
    except BookingError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from None

    seat = await session.get(Seat, booking.seat_id)
    seat_label = seat.label if seat else f"#{booking.seat_id}"
    subject, html = booking_cancelled_html(booking, seat_label)

    background_tasks.add_task(_send_booking_mail, current_user.email, subject, html)

    return booking
