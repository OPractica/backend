from fastapi import APIRouter

from app.core.db import SessionDep
from app.crud.seat import get_active_seats
from app.schemas.schemas import SeatResponse

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatResponse])
async def read_seats(
    session: SessionDep,
    floor: int | None = None,
    zone: str | None = None,
):
    seats = await get_active_seats(session=session, floor=floor, zone=zone)
    return seats
