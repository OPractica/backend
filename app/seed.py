from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Seat


def _du(x, y):
    return [(x + r * 14, y + n * 13) for n in range(3) for r in range(2)]


def _fm(xs, y):
    return [p for x in xs for p in _du(x, y)]


# Same coordinates and order as the SVG floor plan, so seat ids (s1, s2 ...) match the page.
COORDS = (
    _fm([476, 535, 583, 627, 678, 727, 776, 834], 272)
    + _du(595, 341)
    + _fm([495, 546, 604, 685, 725, 774, 835], 402)
    + [(x, 267) for x in [903, 924, 945, 966, 985, 1002]]
    + [(945, 281), (1002, 281)]
    + [(x, 298) for x in [903, 924, 945, 966, 985]]
    + [(900, 410), (921, 410), (944, 410), (966, 410), (1002, 410), (1002, 425), (930, 427)]
    + [(x, 444) for x in [895, 914, 933, 952, 972, 990]]
)


async def seed_seats() -> None:
    async with SessionLocal() as db:
        if await db.scalar(select(func.count()).select_from(Seat)):
            return
        db.add_all(
            Seat(id=f"s{i}", label=("A" if y < 380 else "B") + str(i), x=x, y=y)
            for i, (x, y) in enumerate(COORDS, start=1)
        )
        await db.commit()
