from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import JWT_ALGORITHM, hash_refresh_token, verify_password
from app.crud.user import get_user_by_email
from app.models.database import RefreshToken

pytestmark = pytest.mark.anyio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
INVALID_CREDENTIALS = "invalid email or password"
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


async def register_and_login(client: AsyncClient, data: dict) -> Response:
    await client.post(REGISTER_URL, json=data)
    return await client.post(
        LOGIN_URL, json={"email": data["email"], "password": data["password"]}
    )


async def test_login_returns_tokens(client: AsyncClient, session: AsyncSession):
    data = new_user()

    response = await register_and_login(client, data)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    user = await get_user_by_email(session, data["email"])
    payload = jwt.decode(
        body["access_token"], settings.jwt_secret, algorithms=[JWT_ALGORITHM]
    )
    assert payload["sub"] == str(user.id)
    assert payload["exp"] - payload["iat"] == settings.access_token_minutes * 60


async def test_login_stores_hashed_refresh_token(
    client: AsyncClient, session: AsyncSession
):
    data = new_user()

    response = await register_and_login(client, data)

    refresh_token = response.json()["refresh_token"]
    user = await get_user_by_email(session, data["email"])
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    assert stored is not None
    assert stored.token_hash == hash_refresh_token(refresh_token)
    assert stored.token_hash != refresh_token
    assert stored.revoked_at is None
    lifetime = stored.expires_at - datetime.now(UTC)
    assert timedelta(days=settings.refresh_token_days) - lifetime < timedelta(minutes=1)


async def test_login_wrong_password_returns_401(client: AsyncClient):
    data = new_user()
    await client.post(REGISTER_URL, json=data)

    response = await client.post(
        LOGIN_URL, json={"email": data["email"], "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


async def test_login_unknown_email_returns_401(client: AsyncClient):
    # Same message as for a wrong password, so nobody can check which emails exist
    response = await client.post(
        LOGIN_URL, json={"email": new_user()["email"], "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


async def test_login_inactive_user_returns_403(
    client: AsyncClient, session: AsyncSession
):
    data = new_user()
    await client.post(REGISTER_URL, json=data)
    user = await get_user_by_email(session, data["email"])
    user.is_active = False
    await session.flush()

    response = await client.post(
        LOGIN_URL, json={"email": data["email"], "password": PASSWORD}
    )

    assert response.status_code == 403


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_me_returns_current_user(client: AsyncClient):
    data = new_user()
    token = (await register_and_login(client, data)).json()["access_token"]

    response = await client.get(ME_URL, headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == data["email"]
    assert "password_hash" not in body


async def test_me_without_token_returns_401(client: AsyncClient):
    response = await client.get(ME_URL)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_expired_token_returns_401(client: AsyncClient, session: AsyncSession):
    data = new_user()
    await client.post(REGISTER_URL, json=data)
    user = await get_user_by_email(session, data["email"])
    # Signed like a real token, but it ran out a minute ago
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - timedelta(minutes=16),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )

    response = await client.get(ME_URL, headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "token expired"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_invalid_token_returns_401(client: AsyncClient):
    response = await client.get(ME_URL, headers=bearer("garbage"))

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_inactive_user_returns_403(client: AsyncClient, session: AsyncSession):
    # The token is still valid, but the user was deactivated after login
    data = new_user()
    token = (await register_and_login(client, data)).json()["access_token"]
    user = await get_user_by_email(session, data["email"])
    user.is_active = False
    await session.flush()

    response = await client.get(ME_URL, headers=bearer(token))

    assert response.status_code == 403
