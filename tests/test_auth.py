from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.crud.user import get_user_by_email

pytestmark = pytest.mark.anyio

REGISTER_URL = "/api/v1/auth/register"
PASSWORD = "secret-password"


def new_user() -> dict:
    # A unique email, so tests don't clash with users already in the local database
    return {
        "email": f"{uuid4().hex}@example.com",
        "password": PASSWORD,
        "full_name": "Test User",
    }


async def test_register_returns_created_user(client: AsyncClient):
    data = new_user()

    response = await client.post(REGISTER_URL, json=data)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == data["email"]
    assert body["full_name"] == "Test User"
    assert body["role"] == "employee"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_stores_hashed_password(
    client: AsyncClient, session: AsyncSession
):
    data = new_user()

    await client.post(REGISTER_URL, json=data)

    user = await get_user_by_email(session, data["email"])
    assert user is not None
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)


async def test_register_lowercases_email(client: AsyncClient):
    data = new_user()
    data["email"] = "Test." + data["email"]

    response = await client.post(REGISTER_URL, json=data)

    assert response.status_code == 201
    assert response.json()["email"] == data["email"].lower()


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    data = new_user()
    await client.post(REGISTER_URL, json=data)

    response = await client.post(REGISTER_URL, json=data)

    assert response.status_code == 409


async def test_register_duplicate_email_in_other_case_returns_409(
    client: AsyncClient,
):
    data = new_user()
    await client.post(REGISTER_URL, json=data)

    response = await client.post(
        REGISTER_URL, json=data | {"email": data["email"].upper()}
    )

    assert response.status_code == 409


async def test_register_duplicate_email_race_returns_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    # Two requests at once both pass the email check, the database rejects the second
    data = new_user()
    await client.post(REGISTER_URL, json=data)

    async def email_not_found(session, email):
        return None

    monkeypatch.setattr("app.api.v1.auth.get_user_by_email", email_not_found)
    response = await client.post(REGISTER_URL, json=data)

    assert response.status_code == 409


async def test_register_invalid_email_returns_422(client: AsyncClient):
    response = await client.post(REGISTER_URL, json=new_user() | {"email": "nope"})

    assert response.status_code == 422
