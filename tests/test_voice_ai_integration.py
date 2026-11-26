"""End-to-end HTTP contract: voice transcription -> AI confirmation -> booking.

External Whisper/LLM calls are mocked. Existing test database fixtures are used.
"""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select

from app.ai import chat as ai_chat
from app.ai import memory as ai_memory
from app.ai import tools as ai_tools
from app.ai.agent import build_agent
from app.api.v1 import voice as voice_api
from app.models.database import Booking, Seat
from app.models.voice import VoiceRecord
from app.services.voice import storage, upload
from tests.fakes import ScriptedChatModel, tool_call

START = "2030-01-15T09:00"
END = "2030-01-15T10:00"
SEAT = "7-A01"
TRANSCRIPT = "Найди тихое место у окна с двумя мониторами 15 января 2030 года с 9 до 10"
WAV_DATA = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_voice_ai_booking_requires_confirmation(
    client, session, monkeypatch, tmp_path
):
    """One JWT, two endpoints, one AI session, booking only after consent."""
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(ai_memory, "_fallback", ai_memory._fallback.__class__())

    def fake_voice_process(audio_path, language):
        assert audio_path.is_file()
        assert language == "auto"
        return {
            "transcription": TRANSCRIPT,
            "language": "ru",
            "attributes": {
                "quiet": True,
                "near_window": True,
                "monitors_min": 2,
            },
            "needs_clarification": [],
        }

    monkeypatch.setattr(voice_api, "process_voice_preferences", fake_voice_process)

    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)
    monkeypatch.setattr(ai_memory, "SessionLocal", test_session_local)

    model = ScriptedChatModel(
        responses=[
            tool_call(
                "search_free_seats",
                {"start": START, "end": END},
                call_id="search_1",
            ),
            AIMessage(f"Нашёл место {SEAT}. Забронировать?"),
            tool_call(
                "book_seat",
                {"seat": SEAT, "start": START, "end": END},
                call_id="booking_1",
            ),
            AIMessage(f"Место {SEAT} забронировано."),
        ]
    )
    monkeypatch.setattr(
        ai_chat,
        "build_agent",
        lambda user_id, **options: build_agent(user_id, llm=model, **options),
    )

    seat = Seat(
        label=SEAT,
        floor=7,
        zone="quiet",
        attributes={"quiet": True, "window": True, "monitors": 2},
    )
    session.add(seat)
    await session.flush()

    email = f"voice-integration-{uuid4().hex}@example.com"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret-password", "full_name": "Test User"},
    )
    assert registered.status_code == 201, registered.text
    user_id = registered.json()["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    voice = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("request.wav", WAV_DATA, "audio/wav")},
        headers=headers,
    )
    assert voice.status_code == 201, voice.text
    voice_data = voice.json()
    assert voice_data["transcription"] == TRANSCRIPT
    assert voice_data["language"] == "ru"
    assert voice_data["attributes"]["monitors_min"] == 2
    voice_record = await session.get(VoiceRecord, voice_data["record_id"])
    assert voice_record is not None
    assert voice_record.user_id == user_id

    proposal = await client.post(
        "/api/v1/ai/chat",
        json={"text": voice_data["transcription"]},
        headers=headers,
    )
    assert proposal.status_code == 200, proposal.text
    proposal_data = proposal.json()
    assert SEAT in proposal_data["answer"]
    assert proposal_data["session_id"]
    assert (
        await session.scalar(select(Booking).where(Booking.seat_id == seat.id)) is None
    )

    confirmation = "Да, забронируй 7-A01"
    booked = await client.post(
        "/api/v1/ai/chat",
        json={"text": confirmation, "session_id": proposal_data["session_id"]},
        headers=headers,
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["session_id"] == proposal_data["session_id"]
    assert SEAT in booked.json()["answer"]

    record = await session.scalar(select(Booking).where(Booking.seat_id == seat.id))
    assert record is not None
    assert record.user_id == user_id
    assert record.status == "confirmed"
    assert record.source == "ai"

    my_bookings = await client.get("/api/v1/bookings/me", headers=headers)
    assert my_bookings.status_code == 200, my_bookings.text
    assert any(b["id"] == record.id for b in my_bookings.json())

    first_messages = model.seen[0]
    assert any(
        isinstance(message, HumanMessage) and message.text == TRANSCRIPT
        for message in first_messages
    )
