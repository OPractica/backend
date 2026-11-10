import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path, status

from app.api.deps import CurrentUser
from app.api.openapi import (
    AUTH_RESPONSES,
    error_response,
    example_response,
    rule_or_validation_error,
)
from app.core.db import SessionDep
from app.models.database import Seat
from app.schemas.schemas import BookingCreate, BookingResponse
from app.services.booking import (
    BookingError,
    BookingRuleError,
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


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking",
    description=(
        "Books a seat for a time range and sends a confirmation email. The booking "
        "must start and end on the same working day, inside office hours, and must "
        "not start in the past. Send the time with a UTC offset."
    ),
    responses={
        201: example_response(
            "The booking was created",
            {
                "id": 42,
                "user_id": 1,
                "seat_id": 1,
                "starts_at": "2026-11-12T09:00:00+02:00",
                "ends_at": "2026-11-12T13:00:00+02:00",
                "status": "confirmed",
                "source": "manual",
                "is_checked_in": False,
                "created_at": "2026-11-10T08:15:30+02:00",
            },
        ),
        409: error_response(
            "The seat does not exist, is not available or is already booked "
            "for this time",
            "Seat A-01 is already booked for this time.",
        ),
        422: rule_or_validation_error(
            "A booking rule is broken (office hours, duration, past time, "
            "overlapping booking of the user) or the body is invalid",
            "Office hours are from 09:00 to 19:00.",
        ),
        **AUTH_RESPONSES,
    },
)
async def make_booking(
    booking_in: Annotated[
        BookingCreate,
        Body(
            openapi_examples={
                "manual": {
                    "summary": "Morning booking from the map",
                    "value": {
                        "seat_id": 1,
                        "starts_at": "2026-11-12T09:00:00+02:00",
                        "ends_at": "2026-11-12T13:00:00+02:00",
                        "source": "manual",
                    },
                }
            }
        ),
    ],
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
    except BookingRuleError as err:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from None
    except BookingError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from None

    seat = await session.get(Seat, booking.seat_id)
    seat_label = seat.label if seat else f"#{booking.seat_id}"
    subject, html = booking_confirmed_html(booking, seat_label)

    background_tasks.add_task(_send_booking_mail, current_user.email, subject, html)

    return booking


@router.get(
    "/me",
    response_model=list[BookingResponse],
    summary="List my bookings",
    description="Returns the bookings of the current user.",
    responses={
        200: example_response(
            "Bookings of the current user",
            [
                {
                    "id": 42,
                    "user_id": 1,
                    "seat_id": 1,
                    "starts_at": "2026-11-12T09:00:00+02:00",
                    "ends_at": "2026-11-12T13:00:00+02:00",
                    "status": "confirmed",
                    "source": "manual",
                    "is_checked_in": False,
                    "created_at": "2026-11-10T08:15:30+02:00",
                }
            ],
        ),
        **AUTH_RESPONSES,
    },
)
async def get_my_bookings(session: SessionDep, current_user: CurrentUser):
    return await list_user_bookings(session=session, user_id=current_user.id)


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel my booking",
    description=(
        "Cancels a booking of the current user and sends a cancellation email."
    ),
    responses={
        200: example_response(
            "The booking was cancelled",
            {
                "id": 42,
                "user_id": 1,
                "seat_id": 1,
                "starts_at": "2026-11-12T09:00:00+02:00",
                "ends_at": "2026-11-12T13:00:00+02:00",
                "status": "cancelled",
                "source": "manual",
                "is_checked_in": False,
                "created_at": "2026-11-10T08:15:30+02:00",
            },
        ),
        404: error_response(
            "The booking does not exist, belongs to another user or is already "
            "cancelled",
            "Booking 42 was not found.",
        ),
        **AUTH_RESPONSES,
    },
)
async def cancel_my_booking(
    booking_id: Annotated[int, Path(description="Booking id", examples=[42])],
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
