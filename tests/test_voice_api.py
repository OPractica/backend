from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1 import voice as voice_api
from app.main import app
from app.models.database import User
from app.models.voice import VoiceRecord
from app.services.voice import storage, upload

WAV_DATA = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32

TRANSCRIPTION_RESULT = {
    "transcription": "I need a quiet seat, not near a window",
    "language": "en",
    "attributes": {
        "quiet": True,
        "near_window": False,
    },
    "needs_clarification": [],
}

VOICE_URL = "/api/v1/voice/transcribe"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def voice_storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
async def authenticated_client(
    client: AsyncClient,
    session: AsyncSession,
) -> AsyncIterator[tuple[AsyncClient, User]]:
    user = User(
        email="voice-test@example.com",
        password_hash="test-password-hash",
        full_name="Voice Test User",
        is_active=True,
    )

    session.add(user)
    await session.flush()

    app.dependency_overrides[get_current_user] = lambda: user

    yield client, user


@pytest.fixture
def mock_transcription(monkeypatch):
    def process(file_path, language):
        assert file_path.is_file()
        assert language == "auto"
        return TRANSCRIPTION_RESULT.copy()

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        process,
    )


def make_audio(
    filename="recording.wav",
    content=WAV_DATA,
):
    return {
        "file": (
            filename,
            content,
            "audio/wav",
        )
    }


@pytest.mark.anyio
async def test_voice_requires_authentication(
    client,
    voice_storage_dir,
):
    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 401
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_transcription_success(
    authenticated_client,
    session,
    voice_storage_dir,
    mock_transcription,
):
    client, user = authenticated_client

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["transcription"] == TRANSCRIPTION_RESULT["transcription"]
    assert data["language"] == "en"
    assert data["attributes"]["quiet"] is True
    assert data["attributes"]["near_window"] is False
    assert data["needs_clarification"] == []
    assert data["record_id"] > 0
    assert data["expires_at"]

    record = await session.get(
        VoiceRecord,
        data["record_id"],
    )

    assert record is not None
    assert record.user_id == user.id
    assert record.transcription == data["transcription"]
    assert record.language == data["language"]

    stored_files = list(voice_storage_dir.iterdir())

    assert len(stored_files) == 1
    assert stored_files[0].name == record.audio_path
    assert stored_files[0].read_bytes() == WAV_DATA


@pytest.mark.anyio
async def test_voice_supports_explicit_language(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    def process(file_path, language):
        assert file_path.is_file()
        assert language == "ro"

        return {
            **TRANSCRIPTION_RESULT,
            "transcription": "Vreau un loc linistit",
            "language": "ro",
        }

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        process,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
        data={"language": "ro"},
    )

    assert response.status_code == 201
    assert response.json()["language"] == "ro"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("empty.wav", b""),
        ("document.txt", WAV_DATA),
        ("fake.wav", b"this is not audio"),
    ],
)
async def test_voice_rejects_invalid_audio(
    authenticated_client,
    voice_storage_dir,
    filename,
    content,
):
    client, _ = authenticated_client

    response = await client.post(
        VOICE_URL,
        files=make_audio(filename, content),
    )

    assert response.status_code == 415
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_rejects_oversized_audio(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    monkeypatch.setattr(upload, "MAX_AUDIO_BYTES", 16)

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 413
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_rejects_unsupported_language(
    authenticated_client,
    voice_storage_dir,
):
    client, _ = authenticated_client

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
        data={"language": "fr"},
    )

    assert response.status_code == 422
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_handles_transcription_error(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    def failing_transcription(file_path, language):
        raise ValueError("Transcription is empty")

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        failing_transcription,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 422
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_handles_provider_rate_limit(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    class FakeRateLimitError(Exception):
        pass

    def failing_transcription(file_path, language):
        raise FakeRateLimitError("Rate limit")

    monkeypatch.setattr(
        voice_api,
        "RateLimitError",
        FakeRateLimitError,
    )
    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        failing_transcription,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 429
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_handles_storage_error(
    authenticated_client,
    voice_storage_dir,
    mock_transcription,
    monkeypatch,
):
    client, _ = authenticated_client

    async def failing_save(*args, **kwargs):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        voice_api,
        "save_voice_record",
        failing_save,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 503
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_invalid_result_is_not_saved(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    def invalid_process(file_path, language):
        return {
            **TRANSCRIPTION_RESULT,
            "attributes": "invalid attributes",
        }

    async def unexpected_save(*args, **kwargs):
        pytest.fail("Invalid processing result must not be saved")

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        invalid_process,
    )
    monkeypatch.setattr(
        voice_api,
        "save_voice_record",
        unexpected_save,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 500
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_unserializable_result_is_not_saved(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    client, _ = authenticated_client

    def invalid_process(file_path, language):
        return {
            **TRANSCRIPTION_RESULT,
            "attributes": {"unexpected": object()},
        }

    async def unexpected_save(*args, **kwargs):
        pytest.fail("Unserializable data must not be saved")

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        invalid_process,
    )
    monkeypatch.setattr(
        voice_api,
        "save_voice_record",
        unexpected_save,
    )

    response = await client.post(
        VOICE_URL,
        files=make_audio(),
    )

    assert response.status_code == 500
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_cancellation_keeps_audio_until_worker_finishes(
    authenticated_client,
    voice_storage_dir,
    monkeypatch,
):
    import asyncio
    from threading import Event

    client, _ = authenticated_client
    started = Event()
    release = Event()
    worker_saw_file = []

    def slow_process(file_path, language):
        started.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Test worker was not released")

        worker_saw_file.append(file_path.exists())
        return TRANSCRIPTION_RESULT

    monkeypatch.setattr(
        voice_api,
        "process_voice_preferences",
        slow_process,
    )

    request = asyncio.create_task(client.post(VOICE_URL, files=make_audio()))

    try:
        assert await asyncio.to_thread(started.wait, 3)

        request.cancel()
        await asyncio.sleep(0.1)

        assert len(list(voice_storage_dir.iterdir())) == 1, (
            "Audio was deleted while transcription was still running"
        )
    finally:
        release.set()

        try:
            await asyncio.wait_for(request, timeout=5)
        except asyncio.CancelledError:
            pass

    assert worker_saw_file == [True]
    assert list(voice_storage_dir.iterdir()) == []


@pytest.mark.anyio
async def test_voice_cancellation_after_commit_preserves_audio(
    authenticated_client,
    session,
    voice_storage_dir,
    mock_transcription,
    monkeypatch,
):
    import asyncio

    client, _ = authenticated_client
    committed = asyncio.Event()
    release = asyncio.Event()
    record_ids = []

    original_save = voice_api.save_voice_record

    async def paused_save(*args, **kwargs):
        record = await original_save(*args, **kwargs)
        record_ids.append(record.id)
        committed.set()
        await release.wait()
        return record

    monkeypatch.setattr(
        voice_api,
        "save_voice_record",
        paused_save,
    )

    request = asyncio.create_task(client.post(VOICE_URL, files=make_audio()))

    try:
        await asyncio.wait_for(committed.wait(), timeout=5)

        request.cancel()
        await asyncio.sleep(0.1)

        assert len(list(voice_storage_dir.iterdir())) == 1, (
            "Committed voice record lost its audio file"
        )
    finally:
        release.set()
        try:
            await asyncio.wait_for(request, timeout=5)
        except asyncio.CancelledError:
            pass

    record = await session.get(VoiceRecord, record_ids[0])

    assert record is not None
    assert (voice_storage_dir / record.audio_path).is_file()
