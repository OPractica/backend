from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Seat

pytestmark = pytest.mark.anyio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
BOOKINGS_URL = "/api/v1/bookings"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class FakeEmailSender:
    # Запоминает отправленные письма вместо реальной отправки в сеть

    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    async def send(self, to: str, subject: str, html: str) -> None:
        if self.fail:
            raise RuntimeError("Fake email error")
        self.sent.append((to, subject, html))


async def create_user_and_token(client: AsyncClient) -> tuple[str, str]:
    # Регистрирация тестового пользователя и возвращает (email, token)

    email = f"{uuid4().hex}@example.com"
    password = "secret-password"
    await client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "full_name": "Tester"},
    )
    resp = await client.post(LOGIN_URL, json={"email": email, "password": password})
    return email, resp.json()["access_token"]


async def add_seat(session: AsyncSession) -> Seat:
    # Создание тестовое место в базе
    seat = Seat(label="7-A01", floor=7, zone="window", is_active=True)
    session.add(seat)
    await session.flush()
    return seat


async def test_create_booking_sends_confirmation_email(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake = FakeEmailSender()
    monkeypatch.setattr("app.api.v1.bookings.get_email_sender", lambda: fake)

    email, token = await create_user_and_token(client)
    seat = await add_seat(session)

    response = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json={
            "seat_id": seat.id,
            "starts_at": "2030-01-15T09:00:00Z",
            "ends_at": "2030-01-15T18:00:00Z",
        },
    )

    assert response.status_code == 201
    assert len(fake.sent) == 1
    to, subject, _html = fake.sent[0]
    assert to == email
    assert "confirmed" in subject.lower()
    assert seat.label in subject
    assert seat.label in _html


async def test_cancel_booking_sends_cancellation_email(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake = FakeEmailSender()
    monkeypatch.setattr("app.api.v1.bookings.get_email_sender", lambda: fake)

    email, token = await create_user_and_token(client)
    seat = await add_seat(session)

    # 1. Создаём бронь
    create_resp = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json={
            "seat_id": seat.id,
            "starts_at": "2030-02-15T09:00:00Z",
            "ends_at": "2030-02-15T18:00:00Z",
        },
    )
    booking_id = create_resp.json()["id"]
    fake.sent.clear()

    # 2. Отменяем бронь
    response = await client.patch(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers=bearer(token),
    )

    assert response.status_code == 200
    assert len(fake.sent) == 1
    to, subject, _html = fake.sent[0]
    assert to == email
    assert "cancelled" in subject.lower()
    assert seat.label in subject


async def test_email_error_does_not_break_booking(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    fake = FakeEmailSender(fail=True)
    monkeypatch.setattr("app.api.v1.bookings.get_email_sender", lambda: fake)

    _, token = await create_user_and_token(client)
    seat = await add_seat(session)

    response = await client.post(
        BOOKINGS_URL,
        headers=bearer(token),
        json={
            "seat_id": seat.id,
            "starts_at": "2030-03-15T09:00:00Z",
            "ends_at": "2030-03-15T18:00:00Z",
        },
    )

    # Бронь всё равно должна создаться успешно (201)
    assert response.status_code == 201
    assert response.json()["status"] == "confirmed"
