from datetime import date as Date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import optional_user
from app.db import get_db
from app.models import Seat, User
from app.schemas import AvailOut, SeatOut
from app.services import bookings as svc

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatOut])
async def list_seats(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Seat).where(Seat.is_active).order_by(Seat.id))).all()


@router.get("/availability", response_model=list[AvailOut])
async def availability(
    d: Date = Query(alias="date"), user: User | None = Depends(optional_user), db: AsyncSession = Depends(get_db)
):
    return await svc.availability(db, d, user.id if user else None)
