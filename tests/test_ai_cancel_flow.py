"""Cancelling through the chat: the model asks, the user confirms, the code cancels."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import chat as ai_chat
from app.ai import memory as ai_memory
from app.ai import tools as ai_tools
from app.ai.agent import build_agent, build_system_prompt
from app.models.database import Booking, MeetingRoom, MeetingRoomBooking, Seat, User
from tests.fakes import ScriptedChatModel, tool_call

pytestmark = pytest.mark.anyio

# 07:00-08:00 UTC is 09:00-10:00 in the office in January
STARTS = datetime(2030, 1, 15, 7, tzinfo=UTC)
ENDS = datetime(2030, 1, 15, 8, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def use_test_session(monkeypatch, session: AsyncSession):
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)
    monkeypatch.setattr(ai_memory, "SessionLocal", test_session_local)
    ai_memory._fallback.clear()


@pytest.fixture(autouse=True)
async def sent_mails(monkeypatch) -> list[tuple[str, str]]:
    # No real mail server in tests: remember what would have been sent
    mails = []

    class FakeSender:
        async def send(self, to: str, subject: str, html: str) -> None:
            mails.append((to, html))

    monkeypatch.setattr(ai_tools, "get_email_sender", FakeSender)
    return mails


def use_fake_model(monkeypatch, *responses: AIMessage) -> ScriptedChatModel:
    model = ScriptedChatModel(responses=list(responses))
    monkeypatch.setattr(
        ai_chat,
        "build_agent",
        lambda user_id, **options: build_agent(user_id, llm=model, **options),
    )
    return model


async def make_user(session: AsyncSession) -> User:
    user = User(email=f"{uuid4().hex}@example.com", password_hash="x", full_name="U")
    session.add(user)
    await session.flush()
    return user


async def make_seat_booking(session: AsyncSession, user: User) -> Booking:
    seat = Seat(label=f"T-{uuid4().hex[:6]}", floor=7, zone="window", attributes={})
    session.add(seat)
    await session.flush()
    booking = Booking(user_id=user.id, seat_id=seat.id, starts_at=STARTS, ends_at=ENDS)
    session.add(booking)
    await session.flush()
    return booking


def cancel_call(booking_id: int, call_id: str = "call_1") -> AIMessage:
    return tool_call("cancel_my_booking", {"booking_id": booking_id}, call_id)


async def say(user: User, text: str) -> str:
    answer, _ = await ai_chat.run_chat(user.id, text, session_id="dialog")
    return answer


async def test_cancel_request_only_asks(monkeypatch, session):
    user = await make_user(session)
    booking = await make_seat_booking(session, user)
    use_fake_model(monkeypatch, cancel_call(booking.id), AIMessage("Отменено!"))

    answer = await say(user, "Отмени мою бронь")

    seat = await session.get(Seat, booking.seat_id)
    assert answer == (
        f"Отменить бронь {booking.id}: место {seat.label}, 2030-01-15, "
        "с 09:00 до 10:00?\nОтветьте «да» или «нет»."
    )
    assert booking.status == "confirmed"


async def test_yes_cancels_without_calling_the_model(monkeypatch, session, sent_mails):
    user = await make_user(session)
    booking = await make_seat_booking(session, user)
    model = use_fake_model(
        monkeypatch, cancel_call(booking.id), AIMessage("Подтвердите")
    )

    await say(user, "Отмени мою бронь")
    assert sent_mails == []  # asking sends nothing
    answer = await say(user, "Да")

    assert booking.status == "cancelled"
    [(recipient, html)] = sent_mails
    assert recipient == user.email
    assert "cancelled with AI assistant" in html
    assert answer.startswith(f"Бронь {booking.id} отменена.")
    assert len(model.seen) == 2  # only the first turn used the model


async def test_no_keeps_the_booking(monkeypatch, session):
    user = await make_user(session)
    booking = await make_seat_booking(session, user)
    use_fake_model(monkeypatch, cancel_call(booking.id), AIMessage("Confirmați"))

    await say(user, "Vă rog, anulează rezervarea mea")
    answer = await say(user, "Nu")

    assert booking.status == "confirmed"
    assert answer == "Bine, nu anulez nimic."


async def test_another_message_drops_the_question(monkeypatch, session):
    user = await make_user(session)
    booking = await make_seat_booking(session, user)
    use_fake_model(
        monkeypatch,
        cancel_call(booking.id),
        AIMessage("Please confirm"),
        AIMessage("It is a window seat."),
        AIMessage("Anything else?"),
    )

    await say(user, "Cancel my booking please")
    await say(user, "Which seat is it exactly?")
    answer = await say(user, "yes")

    assert booking.status == "confirmed"
    assert answer == "Anything else?"


async def test_one_yes_cancels_every_asked_booking(monkeypatch, session):
    user = await make_user(session)
    seat_booking = await make_seat_booking(session, user)
    suffix = uuid4().hex[:6]
    room = MeetingRoom(
        office_id=1,
        alias=f"Sala {suffix}",
        email=f"{suffix}@example.com",
        capacity=4,
    )
    session.add(room)
    await session.flush()
    room_booking = MeetingRoomBooking(
        user_id=user.id, room_id=room.id, starts_at=STARTS, ends_at=ENDS
    )
    session.add(room_booking)
    await session.flush()
    both = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "cancel_my_booking",
                "args": {"booking_id": seat_booking.id},
                "id": "a",
            },
            {
                "name": "cancel_meeting_room_booking",
                "args": {"booking_id": room_booking.id},
                "id": "b",
            },
        ],
    )
    use_fake_model(monkeypatch, both, AIMessage("Please confirm"))

    question = await say(user, "Cancel all my bookings please")
    assert seat_booking.status == room_booking.status == "confirmed"
    assert room.alias in question
    answer = await say(user, "Yes, cancel them")

    assert seat_booking.status == room_booking.status == "cancelled"
    assert f"Booking {seat_booking.id} is cancelled." in answer
    assert f"Meeting room booking {room_booking.id} is cancelled." in answer


async def test_someone_elses_booking_is_never_offered(monkeypatch, session):
    user, owner = await make_user(session), await make_user(session)
    foreign = await make_seat_booking(session, owner)
    use_fake_model(
        monkeypatch,
        cancel_call(foreign.id),
        AIMessage("Такой брони нет."),
        AIMessage("Чем помочь?"),
    )

    answer = await say(user, "Отмени чужую бронь")
    await say(user, "да")

    assert answer == "Такой брони нет."
    assert foreign.status == "confirmed"


async def test_booking_cancelled_in_the_meantime_is_reported(monkeypatch, session):
    user = await make_user(session)
    booking = await make_seat_booking(session, user)
    use_fake_model(monkeypatch, cancel_call(booking.id), AIMessage("Подтвердите"))

    await say(user, "Отмени мою бронь")
    booking.status = "cancelled"  # cancelled from the web page
    await session.flush()
    answer = await say(user, "да")

    assert answer.startswith(f"Не удалось отменить бронь {booking.id}")


async def test_cancel_rule_is_only_in_the_confirming_prompt():
    assert "confirmation required" in build_system_prompt(confirm_cancel=True)
    assert "confirmation required" not in build_system_prompt()
