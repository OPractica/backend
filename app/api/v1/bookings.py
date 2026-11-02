from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.schemas.schemas import BookingCreate, BookingResponse
from app.services.booking import (
    BookingError,
    cancel_booking,
    create_booking,
    list_user_bookings,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def make_booking(
    booking_in: BookingCreate, session: SessionDep, current_user: CurrentUser
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
    return booking


@router.get("/me", response_model=list[BookingResponse])
async def get_my_bookings(session: SessionDep, current_user: CurrentUser):
    return await list_user_bookings(session=session, user_id=current_user.id)


@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_my_booking(
    booking_id: int, session: SessionDep, current_user: CurrentUser
):
    try:
        booking = await cancel_booking(
            session=session, user_id=current_user.id, booking_id=booking_id
        )
        await session.commit()
    except BookingError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from None
    return booking
