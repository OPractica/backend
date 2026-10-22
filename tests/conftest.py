from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.database import base


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    # Each test runs inside one transaction that is rolled back at the end,
    # so the local database stays as it was. NullPool because asyncpg
    # connections can't be shared between the event loops of different tests.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        await conn.run_sync(base.metadata.create_all)
        # commit() in the app code only releases a savepoint here
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
