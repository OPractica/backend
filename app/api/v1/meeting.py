from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser
from app.api.errors import APIError
from app.api.openapi import AUTH_RESPONSES, error_response
from app.api.v1.seats import _with_office_tz
from app.core.db import SessionDep
from app.schemas.schemas import (
    MeetingRoomBookingCreate,
    MeetingRoomBookingResponse,
    MeetingRoomWithStatus,
)
from app.services import meeting_room
from app.services.booking import BookingError, BookingRuleError

router = APIRouter(prefix="/meeting", tags=["meeting rooms"])

# Parameter names follow the meeting room API guide
OfficeId = Annotated[int, Query(alias="officeId")]
FromDate = Annotated[datetime, Query(alias="fromDate")]
ToDate = Annotated[datetime, Query(alias="toDate")]

INVALID_RANGE = {
    422: error_response(
        "`fromDate` is not earlier than `toDate`, or a parameter is invalid",
        "fromDate must be earlier than toDate",
        "invalid_time_range",
    )
}


async def _rooms(session, office_id: int, from_date: datetime, to_date: datetime):
    starts_at, ends_at = _with_office_tz(from_date), _with_office_tz(to_date)
    if starts_at >= ends_at:
        raise APIError(
            422, "fromDate must be earlier than toDate", "invalid_time_range"
        )
    return await meeting_room.get_rooms_with_status(
        session, office_id, starts_at, ends_at
    )


@router.get(
    "/getMeetingRoomsWithStatusByOfficeId",
    response_model=list[MeetingRoomWithStatus],
    summary="Meeting rooms of an office with their status",
    description="An unknown office returns []. A time without a zone is office time.",
    responses=INVALID_RANGE,
)
async def read_rooms_with_status(
    session: SessionDep, office_id: OfficeId, from_date: FromDate, to_date: ToDate
):
    return [
        MeetingRoomWithStatus(
            room_id=room.id,
            room_email=room.email,
            room_alias=room.alias,
            room_capacity=str(room.capacity),
            room_equipments=room.equipments,
            is_busy=is_busy,
        )
        for room, is_busy in await _rooms(session, office_id, from_date, to_date)
    ]


@router.get(
    "/getBusyMeetingRoomsByOfficeId",
    response_model=list[int],
    summary="Ids of busy meeting rooms of an office",
    description="[] means every room is free.",
    responses=INVALID_RANGE,
)
async def read_busy_rooms(
    session: SessionDep, office_id: OfficeId, from_date: FromDate, to_date: ToDate
):
    rooms = await _rooms(session, office_id, from_date, to_date)
    return [room.id for room, is_busy in rooms if is_busy]


@router.post(
    "/bookings",
    response_model=MeetingRoomBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a meeting room",
    description="The same office-hours rules as for seat bookings apply.",
    responses={
        409: error_response(
            "The room does not exist or is already booked for this time",
            "Переговорка Orange {kITchen} - Chili уже занята на это время.",
            "room_already_booked",
        ),
        **AUTH_RESPONSES,
    },
)
async def book_room(
    booking_in: MeetingRoomBookingCreate, session: SessionDep, user: CurrentUser
):
    try:
        booking = await meeting_room.create_room_booking(
            session,
            user.id,
            booking_in.room_id,
            booking_in.starts_at,
            booking_in.ends_at,
        )
        await session.commit()
    except BookingRuleError as err:
        raise APIError(422, str(err), err.code) from None
    except BookingError as err:
        raise APIError(409, str(err), err.code) from None
    return booking


@router.get(
    "/bookings/me",
    response_model=list[MeetingRoomBookingResponse],
    summary="My meeting room bookings",
    responses=AUTH_RESPONSES,
)
async def read_my_room_bookings(session: SessionDep, user: CurrentUser):
    return await meeting_room.list_user_room_bookings(session, user.id)


@router.patch(
    "/bookings/{booking_id}/cancel",
    response_model=MeetingRoomBookingResponse,
    summary="Cancel my meeting room booking",
    responses={
        404: error_response(
            "The booking does not exist, is someone else's or is already cancelled",
            "Бронь 7 не найдена.",
            "booking_not_found",
        ),
        **AUTH_RESPONSES,
    },
)
async def cancel_my_room_booking(
    booking_id: int, session: SessionDep, user: CurrentUser
):
    try:
        booking = await meeting_room.cancel_room_booking(session, user.id, booking_id)
        await session.commit()
    except BookingError as err:
        raise APIError(404, str(err), err.code) from None
    return booking
