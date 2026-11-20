import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.anyio

ALLOWED_ORIGIN = settings.cors_origins[0]
PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type",
}


async def test_preflight_from_allowed_origin_is_accepted(client: AsyncClient):
    response = await client.options(
        "/api/v1/bookings",
        headers={"Origin": ALLOWED_ORIGIN, **PREFLIGHT_HEADERS},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


async def test_preflight_from_unknown_origin_gets_no_allow_origin(
    client: AsyncClient,
):
    response = await client.options(
        "/api/v1/bookings",
        headers={"Origin": "https://evil.example.com", **PREFLIGHT_HEADERS},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_simple_request_from_allowed_origin_has_cors_header(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/health/live", headers={"Origin": ALLOWED_ORIGIN}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_origins_are_split_by_comma_from_the_environment(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com ,")

    assert Settings().cors_origins == ["https://a.com", "https://b.com"]
