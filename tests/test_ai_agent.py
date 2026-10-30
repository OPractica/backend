from contextlib import asynccontextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import tools as ai_tools
from app.ai.agent import build_agent, build_system_prompt
from app.models.database import Booking, Seat, User
from tests.fakes import ScriptedChatModel, tool_call

pytestmark = pytest.mark.anyio

START = "2030-01-15T09:00"
END = "2030-01-15T10:00"


@pytest.fixture
async def user(session: AsyncSession) -> User:
    user = User(email="me@example.com", password_hash="x", full_name="Test User")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def seat(session: AsyncSession) -> Seat:
    seat = Seat(label="T-1", floor=7, zone="window", attributes={"quiet": True})
    session.add(seat)
    await session.flush()
    return seat


@pytest.fixture(autouse=True)
async def tools_use_test_session(monkeypatch, session: AsyncSession):
    # The tools open their own database session. Give them the test session,
    # so everything stays inside the rolled-back transaction.
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)


def ask(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_system_prompt_contains_office_time_and_time_zone():
    now = datetime(2030, 1, 15, 9, 30, tzinfo=ZoneInfo("Europe/Chisinau"))

    prompt = build_system_prompt(now)

    assert "2030-01-15 09:30" in prompt
    assert "Europe/Chisinau" in prompt


async def test_agent_sends_system_prompt_and_answers_without_tools(user: User):
    model = ScriptedChatModel(responses=[AIMessage(content="Здравствуйте!")])
    agent = build_agent(user.id, llm=model)

    result = await agent.ainvoke(ask("Привет"))

    assert result["messages"][-1].content == "Здравствуйте!"
    first = model.seen[0][0]
    assert isinstance(first, SystemMessage)
    assert "ассистент по бронированию" in first.content


async def test_agent_calls_search_tool_and_uses_its_result(user: User, seat: Seat):
    model = ScriptedChatModel(
        responses=[
            tool_call("search_free_seats", {"start": START, "end": END}),
            AIMessage(content="Есть место T-1."),
        ]
    )
    agent = build_agent(user.id, llm=model)

    result = await agent.ainvoke(ask("Какие места свободны завтра с 9 до 10?"))

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert "место=T-1" in tool_messages[0].content
    # On the second step the model received the tool result
    assert any(isinstance(m, ToolMessage) for m in model.seen[1])
    assert result["messages"][-1].content == "Есть место T-1."


async def test_agent_books_a_seat_for_the_current_user(
    session: AsyncSession, user: User, seat: Seat
):
    model = ScriptedChatModel(
        responses=[
            tool_call("book_seat", {"seat_id": seat.id, "start": START, "end": END}),
            AIMessage(content="Забронировано."),
        ]
    )
    agent = build_agent(user.id, llm=model)

    await agent.ainvoke(ask("Забронируй T-1 завтра с 9 до 10"))

    booking = await session.scalar(select(Booking).where(Booking.seat_id == seat.id))
    assert booking is not None
    assert booking.user_id == user.id
    assert booking.source == "ai"
    assert booking.starts_at == datetime(2030, 1, 15, 7, tzinfo=UTC)


async def test_agent_passes_tool_errors_back_to_the_model(user: User):
    model = ScriptedChatModel(
        responses=[
            tool_call("book_seat", {"seat_id": 999999, "start": START, "end": END}),
            AIMessage(content="Такого места нет."),
        ]
    )
    agent = build_agent(user.id, llm=model)

    result = await agent.ainvoke(ask("Забронируй место 999999"))

    tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert tool_message.content.startswith("Ошибка:")
    assert result["messages"][-1].content == "Такого места нет."
