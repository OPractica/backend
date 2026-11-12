from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import ollama
import pytest
from httpx import AsyncClient
from langchain_core.exceptions import ModelError, ModelRateLimitError
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import chat as ai_chat
from app.ai import tools as ai_tools
from app.ai.agent import build_agent
from app.models.database import Booking, Seat, User
from tests.fakes import ScriptedChatModel, tool_call

pytestmark = pytest.mark.anyio

CHAT_URL = "/api/v1/ai/chat"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PASSWORD = "secret-password"
START = "2030-01-15T09:00"
END = "2030-01-15T10:00"


@pytest.fixture(autouse=True)
async def tools_use_test_session(monkeypatch, session: AsyncSession):
    # The tools open their own database session. Give them the test session,
    # so everything stays inside the rolled-back transaction.
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)


@pytest.fixture(autouse=True)
def clean_history():
    ai_chat._history.clear()


def use_fake_model(monkeypatch, model: ScriptedChatModel) -> None:
    monkeypatch.setattr(
        ai_chat, "build_agent", lambda user_id: build_agent(user_id, llm=model)
    )


async def register_and_login(client: AsyncClient) -> tuple[dict, int]:
    email = f"{uuid4().hex}@example.com"
    created = await client.post(
        REGISTER_URL,
        json={"email": email, "password": PASSWORD, "full_name": "Test User"},
    )
    login = await client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, created.json()["id"]


async def test_chat_requires_login(client: AsyncClient):
    response = await client.post(CHAT_URL, json={"text": "Привет"})

    assert response.status_code in (401, 403)


async def test_chat_returns_answer_and_session_id(client: AsyncClient, monkeypatch):
    use_fake_model(
        monkeypatch, ScriptedChatModel(responses=[AIMessage("Здравствуйте!")])
    )
    headers, _ = await register_and_login(client)

    response = await client.post(CHAT_URL, json={"text": "Привет"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Здравствуйте!"
    assert body["session_id"]


async def test_chat_keeps_history_inside_one_session(client: AsyncClient, monkeypatch):
    model = ScriptedChatModel(
        responses=[AIMessage("Первый ответ"), AIMessage("Второй ответ")]
    )
    use_fake_model(monkeypatch, model)
    headers, _ = await register_and_login(client)

    first = await client.post(CHAT_URL, json={"text": "Привет"}, headers=headers)
    session_id = first.json()["session_id"]
    await client.post(
        CHAT_URL,
        json={"text": "Давай первое", "session_id": session_id},
        headers=headers,
    )

    second_call = model.seen[1]
    human_texts = [m.text for m in second_call if isinstance(m, HumanMessage)]
    assert human_texts == ["Привет", "Давай первое"]


async def test_chat_does_not_share_a_session_between_users(
    client: AsyncClient, monkeypatch
):
    model = ScriptedChatModel(responses=[AIMessage("Ответ А"), AIMessage("Ответ Б")])
    use_fake_model(monkeypatch, model)
    headers_a, _ = await register_and_login(client)
    headers_b, _ = await register_and_login(client)

    await client.post(
        CHAT_URL, json={"text": "секрет А", "session_id": "shared"}, headers=headers_a
    )
    await client.post(
        CHAT_URL, json={"text": "вопрос Б", "session_id": "shared"}, headers=headers_b
    )

    human_texts = [m.text for m in model.seen[1] if isinstance(m, HumanMessage)]
    assert human_texts == ["вопрос Б"]


async def test_agent_books_for_the_logged_in_user(
    client: AsyncClient, session: AsyncSession, monkeypatch
):
    seat = Seat(label="T-1", floor=7, zone="window", attributes={})
    session.add(seat)
    await session.flush()
    model = ScriptedChatModel(
        responses=[
            tool_call("book_seat", {"seat_id": seat.id, "start": START, "end": END}),
            AIMessage("Забронировано."),
        ]
    )
    use_fake_model(monkeypatch, model)
    headers, user_id = await register_and_login(client)

    await client.post(CHAT_URL, json={"text": "Забронируй T-1"}, headers=headers)

    booking = await session.scalar(select(Booking).where(Booking.seat_id == seat.id))
    assert booking is not None
    assert booking.user_id == user_id
    assert booking.source == "ai"


async def test_agent_cannot_cancel_another_users_booking(
    client: AsyncClient, session: AsyncSession, monkeypatch
):
    seat = Seat(label="T-1", floor=7, zone="window", attributes={})
    owner = User(
        email=f"{uuid4().hex}@example.com", password_hash="x", full_name="Owner"
    )
    session.add_all([seat, owner])
    await session.flush()
    foreign = Booking(
        user_id=owner.id,
        seat_id=seat.id,
        starts_at=datetime(2030, 1, 15, 7, tzinfo=UTC),
        ends_at=datetime(2030, 1, 15, 8, tzinfo=UTC),
    )
    session.add(foreign)
    await session.flush()
    model = ScriptedChatModel(
        responses=[
            tool_call("cancel_my_booking", {"booking_id": foreign.id}),
            AIMessage("Не получилось."),
        ]
    )
    use_fake_model(monkeypatch, model)
    headers, _ = await register_and_login(client)

    await client.post(CHAT_URL, json={"text": "Отмени бронь"}, headers=headers)

    assert foreign.status == "confirmed"


async def test_chat_returns_429_when_the_model_is_rate_limited(
    client: AsyncClient, monkeypatch
):
    model = ScriptedChatModel(responses=[], errors=[ModelRateLimitError("limit")])
    use_fake_model(monkeypatch, model)
    headers, _ = await register_and_login(client)

    response = await client.post(CHAT_URL, json={"text": "Привет"}, headers=headers)

    assert response.status_code == 429


async def test_chat_returns_503_when_the_model_fails(client: AsyncClient, monkeypatch):
    model = ScriptedChatModel(responses=[], errors=[ModelError("boom")])
    use_fake_model(monkeypatch, model)
    headers, _ = await register_and_login(client)

    response = await client.post(CHAT_URL, json={"text": "Привет"}, headers=headers)

    assert response.status_code == 503


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "x" * 2001}, {}])
async def test_chat_rejects_invalid_input(client: AsyncClient, body: dict):
    headers, _ = await register_and_login(client)

    response = await client.post(CHAT_URL, json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("timed out"),
        ollama.ResponseError("model not found"),
    ],
)
async def test_chat_returns_503_when_the_local_model_server_fails(
    client: AsyncClient, monkeypatch, error: Exception
):
    model = ScriptedChatModel(responses=[], errors=[error])
    use_fake_model(monkeypatch, model)
    headers, _ = await register_and_login(client)

    response = await client.post(CHAT_URL, json={"text": "Привет"}, headers=headers)

    assert response.status_code == 503
