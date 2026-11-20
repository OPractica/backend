import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.database import Seat, User
from app.services.booking import BookingError, create_booking
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.anyio

STARTS_AT = datetime(2030, 1, 15, 9, tzinfo=UTC)
ENDS_AT = datetime(2030, 1, 15, 10, tzinfo=UTC)


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # Separate connections with real commits: a race needs two transactions
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_simultaneous_booking_of_same_seat_raises_seat_already_booked(
    sessions: async_sessionmaker[AsyncSession],
):
    async with sessions() as setup:
        seat = Seat(label=f"race-{uuid4().hex[:8]}", floor=7, zone="window")
        users = [
            User(email=f"{uuid4().hex}@example.com", password_hash="x", full_name="U")
            for _ in range(2)
        ]
        setup.add_all([seat, *users])
        await setup.commit()

    try:
        async with sessions() as first, sessions() as second:
            # The first booking is inserted but not committed yet, so the second
            # one passes the overlap check and waits on the database constraint
            await create_booking(first, users[0].id, seat.id, STARTS_AT, ENDS_AT)
            racing = asyncio.create_task(
                create_booking(second, users[1].id, seat.id, STARTS_AT, ENDS_AT)
            )
            await asyncio.sleep(0.2)
            await first.commit()

            with pytest.raises(BookingError) as err:
                await racing
            assert err.value.code == "seat_already_booked"
    finally:
        async with sessions() as cleanup:
            # Bookings go away with the seat and the users (ON DELETE CASCADE)
            await cleanup.execute(delete(Seat).where(Seat.id == seat.id))
            await cleanup.execute(
                delete(User).where(User.id.in_([u.id for u in users]))
            )
            await cleanup.commit()
