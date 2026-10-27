from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.db import SessionDep
from app.crud.seat import get_active_seats
from app.schemas.schemas import SeatAvailability, SeatResponse
from app.services.booking import get_seats_availability

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatResponse])
async def read_seats(
    session: SessionDep,
    floor: int | None = None,
    zone: str | None = None,
):
    seats = await get_active_seats(session=session, floor=floor, zone=zone)
    return seats


def _with_office_tz(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=ZoneInfo(settings.office_timezone))
    return moment


@router.get("/availability", response_model=list[SeatAvailability])
async def read_availability(
    session: SessionDep, starts_at: datetime, ends_at: datetime
):
    starts_at = _with_office_tz(starts_at)
    ends_at = _with_office_tz(ends_at)
    if starts_at >= ends_at:
        raise HTTPException(
            status_code=422, detail="starts_at must be earlier than ends_at"
        )

    rows = await get_seats_availability(session, starts_at, ends_at)
    return [
        SeatAvailability(
            id=row.id, label=row.label, status="booked" if row.is_booked else "free"
        )
        for row in rows
    ]
