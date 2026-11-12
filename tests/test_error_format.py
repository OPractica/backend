import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_booking_emails import (
    BOOKINGS_URL,
    add_seat,
    bearer,
    create_user_and_token,
)

pytestmark = pytest.mark.anyio

LOGIN_URL = "/api/v1/auth/login"


def booking_body(seat_id: int, starts_at: str, ends_at: str) -> dict:
    return {"seat_id": seat_id, "starts_at": starts_at, "ends_at": ends_at}


async def test_missing_token_has_unauthorized_code(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert isinstance(response.json()["detail"], str)


async def test_invalid_token_has_invalid_token_code(client: AsyncClient):
    response = await client.get("/api/v1/auth/me", headers=bearer("garbage"))

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid token", "code": "invalid_token"}


async def test_wrong_password_has_invalid_credentials_code(client: AsyncClient):
    response = await client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "x"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_validation_error_keeps_list_detail_and_has_code(client: AsyncClient):
    response = await client.post(LOGIN_URL, json={"email": "not-an-email"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert isinstance(body["detail"], list)
    assert {"type", "loc", "msg"} <= body["detail"][0].keys()


async def test_unknown_route_has_not_found_code(client: AsyncClient):
    response = await client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_availability_with_reversed_interval_has_code(client: AsyncClient):
    response = await client.get(
        "/api/v1/seats/availability",
        params={"starts_at": "2030-01-15T10:00:00Z", "ends_at": "2030-01-15T09:00:00Z"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_time_range"


async def test_booking_in_the_past_has_rule_code(
    client: AsyncClient, session: AsyncSession
):
    _, token = await create_user_and_token(client)
    seat = await add_seat(session)

    response = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json=booking_body(seat.id, "2020-01-15T09:00:00Z", "2020-01-15T10:00:00Z"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "booking_in_past"


async def test_booking_outside_office_hours_has_rule_code(
    client: AsyncClient, session: AsyncSession
):
    _, token = await create_user_and_token(client)
    seat = await add_seat(session)

    response = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json=booking_body(seat.id, "2030-01-15T03:00:00Z", "2030-01-15T04:00:00Z"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "outside_office_hours"


async def test_booking_unknown_seat_has_seat_not_found_code(client: AsyncClient):
    _, token = await create_user_and_token(client)

    response = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json=booking_body(999999, "2030-01-15T09:00:00Z", "2030-01-15T10:00:00Z"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "seat_not_found"


async def test_booking_taken_seat_has_seat_already_booked_code(
    client: AsyncClient, session: AsyncSession
):
    _, first_token = await create_user_and_token(client)
    _, second_token = await create_user_and_token(client)
    seat = await add_seat(session)
    body = booking_body(seat.id, "2030-01-15T09:00:00Z", "2030-01-15T10:00:00Z")

    first = await client.post(BOOKINGS_URL, headers=bearer(first_token), json=body)
    second = await client.post(BOOKINGS_URL, headers=bearer(second_token), json=body)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "seat_already_booked"


async def test_cancel_unknown_booking_has_booking_not_found_code(
    client: AsyncClient,
):
    _, token = await create_user_and_token(client)

    response = await client.patch(
        f"{BOOKINGS_URL}/999999/cancel", headers=bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == "booking_not_found"
