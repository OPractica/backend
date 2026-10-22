from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import get_session
from app.main import app

pytestmark = pytest.mark.anyio


async def test_liveness_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_with_database_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_without_database_returns_503(client: AsyncClient):
    # Nothing listens on port 1, so connecting to the database fails
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost:1/test", poolclass=NullPool
    )

    async def unreachable_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = unreachable_session

    response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    await engine.dispose()
