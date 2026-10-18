from typing import List, Optional
from fastapi import APIRouter

from app.core.db import SessionDep
from app.schemas.schemas import SeatResponse
from app.crud.seat import get_active_seats

router = APIRouter(prefix="/seats", tags=["seats"])

@router.get("", response_model=List[SeatResponse])
async def read_seats(
        session: SessionDep,
        floor: Optional[int] = None,
        zone: Optional[str] = None,
):
    seats = await get_active_seats(session=session, floor=floor, zone=zone)
    return seats

