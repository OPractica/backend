from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice import VoiceRecord
from app.services.voice import storage


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_save_voice_record_sets_24_hour_expiration(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)

    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"test audio")

    session = MagicMock(spec=AsyncSession)

    record = await storage.save_voice_record(
        session=session,
        audio_path=audio_path,
        text="  Hello world  ",
        language="en",
    )

    assert record.audio_path == "recording.wav"
    assert record.transcription == "Hello world"
    assert record.language == "en"
    assert record.expires_at - record.created_at == timedelta(hours=24)

    session.add.assert_called_once_with(record)
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_save_voice_record_rejects_external_file(tmp_path, monkeypatch):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    monkeypatch.setattr(storage, "STORAGE_DIR", storage_dir)

    audio_path = tmp_path / "external.wav"
    audio_path.write_bytes(b"test audio")

    session = MagicMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="storage directory"):
        await storage.save_voice_record(
            session=session,
            audio_path=audio_path,
            text="Hello",
            language="en",
        )

    session.add.assert_not_called()


@pytest.mark.anyio
async def test_save_voice_record_rolls_back_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)

    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"test audio")

    session = MagicMock(spec=AsyncSession)
    session.commit.side_effect = RuntimeError("Database error")

    with pytest.raises(RuntimeError, match="Database error"):
        await storage.save_voice_record(
            session=session,
            audio_path=audio_path,
            text="Hello",
            language="en",
        )

    session.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_delete_expired_records_removes_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)

    audio_path = tmp_path / "expired.wav"
    audio_path.write_bytes(b"old audio")

    now = datetime.now(UTC)

    record = VoiceRecord(
        audio_path="expired.wav",
        transcription="Old recording",
        language="en",
        created_at=now - timedelta(hours=25),
        expires_at=now - timedelta(hours=1),
    )
    record.id = 1

    session = MagicMock(spec=AsyncSession)

    result = MagicMock()
    result.all.return_value = [record]
    session.scalars.return_value = result

    @asynccontextmanager
    async def fake_session_local():
        yield session

    monkeypatch.setattr(storage, "SessionLocal", fake_session_local)

    deleted_count = await storage.delete_expired_records()

    assert deleted_count == 1
    assert not audio_path.exists()

    session.delete.assert_awaited_once_with(record)
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_delete_expired_records_keeps_record_on_file_error(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)

    audio_path = tmp_path / "locked.wav"
    audio_path.write_bytes(b"test audio")

    now = datetime.now(UTC)

    record = VoiceRecord(
        audio_path="locked.wav",
        transcription="Test recording",
        language="en",
        created_at=now - timedelta(hours=25),
        expires_at=now - timedelta(hours=1),
    )
    record.id = 2

    session = MagicMock(spec=AsyncSession)

    result = MagicMock()
    result.all.return_value = [record]
    session.scalars.return_value = result

    @asynccontextmanager
    async def fake_session_local():
        yield session

    async def failing_to_thread(func, *args, **kwargs):
        raise PermissionError("File is locked")

    monkeypatch.setattr(storage, "SessionLocal", fake_session_local)
    monkeypatch.setattr(storage.asyncio, "to_thread", failing_to_thread)

    deleted_count = await storage.delete_expired_records()

    assert deleted_count == 0
    assert audio_path.exists()

    session.delete.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_delete_expired_records_rejects_unsafe_path(tmp_path, monkeypatch):
    storage_dir = tmp_path / "audio_storage"
    storage_dir.mkdir()

    monkeypatch.setattr(storage, "STORAGE_DIR", storage_dir)

    outside_file = tmp_path / "outside.wav"
    outside_file.write_bytes(b"important audio")

    now = datetime.now(UTC)

    record = VoiceRecord(
        audio_path="../outside.wav",
        transcription="Test recording",
        language="en",
        created_at=now - timedelta(hours=25),
        expires_at=now - timedelta(hours=1),
    )
    record.id = 3

    session = MagicMock(spec=AsyncSession)

    result = MagicMock()
    result.all.return_value = [record]
    session.scalars.return_value = result

    @asynccontextmanager
    async def fake_session_local():
        yield session

    monkeypatch.setattr(storage, "SessionLocal", fake_session_local)

    deleted_count = await storage.delete_expired_records()

    assert deleted_count == 0
    assert outside_file.exists()

    session.delete.assert_not_awaited()
    session.commit.assert_awaited_once()
