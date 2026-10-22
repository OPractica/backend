from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.database import base

# Tests use their own database on the same server: office_booking -> office_booking_test
DATABASE_URL = make_url(settings.database_url)
TEST_DATABASE_URL = DATABASE_URL.set(database=f"{DATABASE_URL.database}_test")


@pytest.fixture(scope="session", autouse=True)
def test_database():
    # Create the test database if it's missing and rebuild its tables once per run
    sync_url = TEST_DATABASE_URL.set(drivername="postgresql+psycopg")
    server = create_engine(
        sync_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with server.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE_URL.database},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"'))
    server.dispose()

    engine = create_engine(sync_url)
    base.metadata.drop_all(engine)
    base.metadata.create_all(engine)
    engine.dispose()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    # Each test runs inside one transaction that is rolled back at the end,
    # so tests don't see each other's data. NullPool because asyncpg
    # connections can't be shared between the event loops of different tests.
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        transaction = await conn.begin()
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
