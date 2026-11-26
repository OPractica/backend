import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import memory
from app.models.chat import ChatSession
from app.models.database import User

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def use_test_session(monkeypatch, session: AsyncSession):
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(memory, "SessionLocal", test_session_local)
    memory._fallback.clear()


async def add_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Test")
    session.add(user)
    await session.flush()
    return user


def gemini_like_turn() -> list:
    """Реальный вид сообщений: ответ модели с блоками, подписью и вызовом инструмента."""
    return [
        HumanMessage("Забронируй T-1"),
        AIMessage(
            content=[
                {"type": "text", "text": "", "extras": {"signature": "c2lnbmF0dXJl"}}
            ],
            tool_calls=[
                {
                    "name": "book_seat",
                    "args": {"seat": "T-1"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="booking created", name="book_seat", tool_call_id="call_1"),
        AIMessage("Готово"),
    ]


async def test_history_survives_a_server_restart(session):
    user = await add_user(session, "memory-a@example.com")
    await memory.save_history(user.id, "s1", gemini_like_turn())

    memory._fallback.clear()  # так выглядит перезапуск сервера
    restored = await memory.load_history(user.id, "s1")

    assert [type(m) for m in restored] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    assert restored[1].tool_calls[0]["name"] == "book_seat"
    assert restored[1].content[0]["extras"]["signature"] == "c2lnbmF0dXJl"
    assert restored[3].text == "Готово"


async def test_saved_messages_are_plain_json(session):
    user = await add_user(session, "memory-b@example.com")
    await memory.save_history(user.id, "s1", gemini_like_turn())

    stored = await session.scalar(select(ChatSession.messages))
    assert json.loads(json.dumps(stored)) == stored


async def test_saving_twice_updates_one_row(session):
    user = await add_user(session, "memory-c@example.com")
    await memory.save_history(user.id, "s1", [HumanMessage("a")])
    await memory.save_history(user.id, "s1", [HumanMessage("a"), AIMessage("b")])

    rows = list(await session.scalars(select(ChatSession)))
    assert len(rows) == 1
    assert len(await memory.load_history(user.id, "s1")) == 2


async def test_sessions_of_different_users_are_separate(session):
    first = await add_user(session, "memory-d1@example.com")
    second = await add_user(session, "memory-d2@example.com")
    await memory.save_history(first.id, "shared", [HumanMessage("secret")])
    memory._fallback.clear()

    assert await memory.load_history(second.id, "shared") == []


async def test_unknown_session_is_empty(session):
    user = await add_user(session, "memory-e@example.com")
    assert await memory.load_history(user.id, "nothing") == []


async def test_old_dialogs_of_the_user_are_deleted_on_save(session):
    user = await add_user(session, "memory-f@example.com")
    await memory.save_history(user.id, "old", [HumanMessage("old")])
    await session.execute(
        update(ChatSession).values(updated_at=datetime.now(UTC) - timedelta(days=8))
    )

    await memory.save_history(user.id, "new", [HumanMessage("new")])

    sessions = list(await session.scalars(select(ChatSession.session_id)))
    assert sessions == ["new"]


async def test_trim_keeps_the_tail_and_starts_with_a_user_message():
    messages = []
    for i in range(40):
        messages += [
            HumanMessage(f"q{i}"),
            AIMessage(
                content="", tool_calls=[{"name": "t", "args": {}, "id": f"c{i}"}]
            ),
            ToolMessage(content="r", name="t", tool_call_id=f"c{i}"),
            AIMessage(f"a{i}"),
        ]

    trimmed = memory.trim_history(messages)

    assert len(trimmed) <= memory.MAX_MESSAGES
    assert isinstance(trimmed[0], HumanMessage)
    assert trimmed[-1].text == "a39"


async def test_short_history_is_not_trimmed():
    messages = [HumanMessage("a"), AIMessage("b")]
    assert memory.trim_history(messages) == messages


async def test_database_failure_falls_back_to_process_memory(monkeypatch):
    @asynccontextmanager
    async def broken_session():
        raise OperationalError("select", {}, Exception("db is down"))
        yield

    monkeypatch.setattr(memory, "SessionLocal", broken_session)

    await memory.save_history(1, "s1", [HumanMessage("hi"), AIMessage("hello")])
    restored = await memory.load_history(1, "s1")

    assert [m.text for m in restored] == ["hi", "hello"]
