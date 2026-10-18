
# Вытаскивает из базы готовые объекты Seat
# по фильтрам floor и zone.


# ---- надо будет путь поменять в случае чего


from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Seat


async def get_active_seats(
        session: AsyncSession,
        floor: Optional[int] = None,
        zone: Optional[str] = None
) -> Sequence[Seat]:
    query = select(Seat).where(Seat.is_active == True)

    if floor is not None:
        query = query.where(Seat.floor == floor)

    if zone is not None:
        query = query.where(Seat.zone == zone)

    result = await session.execute(query)
    return result.scalars().all()
