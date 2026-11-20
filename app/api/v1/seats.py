from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.api.errors import APIError
from app.api.openapi import example_response, rule_or_validation_error
from app.core.config import settings
from app.core.db import SessionDep
from app.crud.seat import get_active_seats
from app.schemas.schemas import SeatAvailability, SeatResponse
from app.services.booking import get_seats_availability

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get(
    "",
    response_model=list[SeatResponse],
    summary="List seats",
    description="Returns all active seats, optionally filtered by floor and zone.",
    responses={
        200: example_response(
            "Active seats",
            [
                {
                    "id": 1,
                    "label": "A-01",
                    "floor": 1,
                    "zone": "A",
                    "is_active": True,
                    "attributes": {"monitor": True, "window": False},
                }
            ],
        )
    },
)
async def read_seats(
    session: SessionDep,
    floor: Annotated[
        int | None, Query(description="Only seats on this floor", examples=[1])
    ] = None,
    zone: Annotated[
        str | None, Query(description="Only seats in this zone", examples=["A"])
    ] = None,
):
    seats = await get_active_seats(session=session, floor=floor, zone=zone)
    return seats


def _with_office_tz(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=ZoneInfo(settings.office_timezone))
    return moment


@router.get(
    "/availability",
    response_model=list[SeatAvailability],
    summary="Get seat availability for a time range",
    description=(
        "Returns every active seat with its status (`free` or `booked`) for the "
        "given time range. A time without a time zone is treated as office time."
    ),
    responses={
        200: example_response(
            "Seats with their status for the time range",
            [
                {"id": 1, "label": "A-01", "status": "free"},
                {"id": 2, "label": "A-02", "status": "booked"},
            ],
        ),
        422: rule_or_validation_error(
            "`starts_at` is not earlier than `ends_at`, or a parameter is invalid",
            "starts_at must be earlier than ends_at",
            "invalid_time_range",
        ),
    },
)
async def read_availability(
    session: SessionDep,
    starts_at: Annotated[
        datetime,
        Query(
            description="Start of the time range (ISO 8601)",
            examples=["2026-11-12T09:00:00+02:00"],
        ),
    ],
    ends_at: Annotated[
        datetime,
        Query(
            description="End of the time range (ISO 8601)",
            examples=["2026-11-12T11:00:00+02:00"],
        ),
    ],
):
    starts_at = _with_office_tz(starts_at)
    ends_at = _with_office_tz(ends_at)
    if starts_at >= ends_at:
        raise APIError(
            status_code=422,
            detail="starts_at must be earlier than ends_at",
            code="invalid_time_range",
        )

    rows = await get_seats_availability(session, starts_at, ends_at)
    return [
        SeatAvailability(
            id=row.id, label=row.label, status="booked" if row.is_booked else "free"
        )
        for row in rows
    ]
