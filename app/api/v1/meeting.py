from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUser
from app.api.errors import APIError
from app.api.openapi import (
    AUTH_RESPONSES,
    error_response,
    example_response,
    rule_or_validation_error,
)
from app.api.v1.seats import _with_office_tz
from app.core.db import SessionDep
from app.schemas.schemas import (
    MeetingRoomBookingCreate,
    MeetingRoomBookingResponse,
    MeetingRoomWithStatus,
)
from app.services.booking import BookingError, BookingRuleError
from app.services.meeting_room import (
    cancel_room_booking,
    create_room_booking,
    get_busy_room_ids,
    get_rooms_with_status,
    list_user_room_bookings,
)

router = APIRouter(prefix="/meeting", tags=["meeting rooms"])

OfficeId = Annotated[
    int, Query(alias="officeId", description="Office id", examples=[1])
]
FromDate = Annotated[
    datetime,
    Query(
        alias="fromDate",
        description="Start of the time range (ISO 8601)",
        examples=["2026-11-16T09:00:00Z"],
    ),
]
ToDate = Annotated[
    datetime,
    Query(
        alias="toDate",
        description="End of the time range (ISO 8601)",
        examples=["2026-11-16T09:30:00Z"],
    ),
]

INVALID_RANGE_RESPONSE = rule_or_validation_error(
    "`fromDate` is not earlier than `toDate`, or a parameter is invalid",
    "fromDate must be earlier than toDate",
    "invalid_time_range",
)

BOOKING_EXAMPLE = {
    "id": 7,
    "room_id": 10301,
    "user_id": 1,
    "starts_at": "2026-11-16T09:00:00Z",
    "ends_at": "2026-11-16T09:30:00Z",
    "status": "confirmed",
    "created_at": "2026-11-15T12:00:00Z",
}


def _time_range(from_date: datetime, to_date: datetime) -> tuple[datetime, datetime]:
    from_date = _with_office_tz(from_date)
    to_date = _with_office_tz(to_date)
    if from_date >= to_date:
        raise APIError(
            status_code=422,
            detail="fromDate must be earlier than toDate",
            code="invalid_time_range",
        )
    return from_date, to_date


@router.get(
    "/getMeetingRoomsWithStatusByOfficeId",
    response_model=list[MeetingRoomWithStatus],
    summary="List meeting rooms of an office with their status",
    description=(
        "Returns every active meeting room of the office and whether it is busy in "
        "the time range. An unknown office returns an empty list. A time without a "
        "time zone is treated as office time."
    ),
    responses={
        200: example_response(
            "Meeting rooms with their status",
            [
                {
                    "roomId": 10301,
                    "roomEmail": "chili@orange.md",
                    "roomAlias": "Orange {kITchen} - Chili",
                    "roomCapacity": "10",
                    "roomEquipments": "Room, TV, Whiteboard",
                    "isBusy": True,
                }
            ],
        ),
        422: INVALID_RANGE_RESPONSE,
    },
)
async def read_rooms_with_status(
    session: SessionDep, office_id: OfficeId, from_date: FromDate, to_date: ToDate
):
    starts_at, ends_at = _time_range(from_date, to_date)
    rows = await get_rooms_with_status(session, office_id, starts_at, ends_at)
    return [
        MeetingRoomWithStatus(
            room_id=room.id,
            room_email=room.email,
            room_alias=room.alias,
            room_capacity=str(room.capacity),
            room_equipments=room.equipments,
            is_busy=is_busy,
        )
        for room, is_busy in rows
    ]


@router.get(
    "/getBusyMeetingRoomsByOfficeId",
    response_model=list[int],
    summary="List busy meeting rooms of an office",
    description=(
        "Returns the ids of the office's meeting rooms that are busy in the time "
        "range. An empty list means every room is free."
    ),
    responses={
        200: example_response("Ids of busy rooms", [10301, 10304]),
        422: INVALID_RANGE_RESPONSE,
    },
)
async def read_busy_rooms(
    session: SessionDep, office_id: OfficeId, from_date: FromDate, to_date: ToDate
):
    starts_at, ends_at = _time_range(from_date, to_date)
    return await get_busy_room_ids(session, office_id, starts_at, ends_at)


@router.post(
    "/bookings",
    response_model=MeetingRoomBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a meeting room",
    description=(
        "Books a meeting room for a time range. The same office-hours rules as for "
        "seats apply. Send the time with a UTC offset."
    ),
    responses={
        201: example_response("The booking was created", BOOKING_EXAMPLE),
        409: error_response(
            "The room does not exist, is not active or is already booked for this time",
            "Переговорка Orange {kITchen} - Chili уже занята на это время.",
            "room_already_booked",
        ),
        422: rule_or_validation_error(
            "A booking rule is broken (office hours, duration, past time) or the "
            "body is invalid",
            "Офис закрыт по выходным.",
            "office_closed_weekend",
        ),
        **AUTH_RESPONSES,
    },
)
async def book_room(
    booking_in: MeetingRoomBookingCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        booking = await create_room_booking(
            session=session,
            user_id=current_user.id,
            room_id=booking_in.room_id,
            starts_at=booking_in.starts_at,
            ends_at=booking_in.ends_at,
        )
        await session.commit()
    except BookingRuleError as err:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err), code=err.code
        ) from None
    except BookingError as err:
        raise APIError(
            status.HTTP_409_CONFLICT, detail=str(err), code=err.code
        ) from None
    return booking


@router.get(
    "/bookings/me",
    response_model=list[MeetingRoomBookingResponse],
    summary="List my meeting room bookings",
    responses={
        200: example_response(
            "Meeting room bookings of the current user", [BOOKING_EXAMPLE]
        ),
        **AUTH_RESPONSES,
    },
)
async def read_my_room_bookings(session: SessionDep, current_user: CurrentUser):
    return await list_user_room_bookings(session, current_user.id)


@router.patch(
    "/bookings/{booking_id}/cancel",
    response_model=MeetingRoomBookingResponse,
    summary="Cancel my meeting room booking",
    responses={
        200: example_response(
            "The booking was cancelled", {**BOOKING_EXAMPLE, "status": "cancelled"}
        ),
        404: error_response(
            "The booking does not exist, belongs to another user or is already "
            "cancelled",
            "Бронь 7 не найдена.",
            "booking_not_found",
        ),
        **AUTH_RESPONSES,
    },
)
async def cancel_my_room_booking(
    booking_id: Annotated[int, Path(description="Booking id", examples=[7])],
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        booking = await cancel_room_booking(session, current_user.id, booking_id)
        await session.commit()
    except BookingError as err:
        raise APIError(
            status.HTTP_404_NOT_FOUND, detail=str(err), code=err.code
        ) from None
    return booking
