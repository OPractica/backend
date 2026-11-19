from io import BytesIO

import pytest
from fastapi import UploadFile

from app.services.voice import upload
from app.services.voice.upload import (
    AudioTooLargeError,
    InvalidAudioError,
    save_uploaded_audio,
)

# Minimal WAV-like data for testing file validation.
# This is not a real audio recording.
WAV_DATA = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_upload(
    filename: str,
    content: bytes,
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
    )


@pytest.mark.anyio
async def test_upload_valid_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    audio = make_upload("recording.wav", WAV_DATA)

    try:
        path = await save_uploaded_audio(audio)

        assert path.exists()
        assert path.parent == tmp_path
        assert path.suffix == ".wav"
        assert path.read_bytes() == WAV_DATA
        assert path.name != "recording.wav"
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_rejects_empty_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    audio = make_upload("empty.wav", b"")

    try:
        with pytest.raises(InvalidAudioError, match="empty"):
            await save_uploaded_audio(audio)

        assert list(tmp_path.iterdir()) == []
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_rejects_unsupported_extension(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    audio = make_upload("document.exe", WAV_DATA)

    try:
        with pytest.raises(InvalidAudioError, match="Unsupported"):
            await save_uploaded_audio(audio)

        assert list(tmp_path.iterdir()) == []
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_rejects_fake_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    audio = make_upload(
        "fake.wav",
        b"This is not a WAV audio file",
    )

    try:
        with pytest.raises(InvalidAudioError, match="content"):
            await save_uploaded_audio(audio)

        assert list(tmp_path.iterdir()) == []
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_rejects_oversized_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(upload, "MAX_AUDIO_BYTES", 16)

    audio = make_upload("large.wav", WAV_DATA)

    try:
        with pytest.raises(AudioTooLargeError):
            await save_uploaded_audio(audio)

        assert list(tmp_path.iterdir()) == []
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_ignores_unsafe_filename(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    audio = make_upload("../../outside.wav", WAV_DATA)

    try:
        path = await save_uploaded_audio(audio)

        assert path.exists()
        assert path.parent == tmp_path
        assert ".." not in path.parts
        assert path.name != "outside.wav"
    finally:
        await audio.close()


@pytest.mark.anyio
async def test_upload_generates_unique_filenames(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    first = make_upload("recording.wav", WAV_DATA)
    second = make_upload("recording.wav", WAV_DATA)

    try:
        first_path = await save_uploaded_audio(first)
        second_path = await save_uploaded_audio(second)

        assert first_path != second_path
        assert first_path.exists()
        assert second_path.exists()
    finally:
        await first.close()
        await second.close()


@pytest.mark.anyio
async def test_upload_cancellation_removes_partial_file(
    tmp_path,
    monkeypatch,
):
    import asyncio

    monkeypatch.setattr(upload, "STORAGE_DIR", tmp_path)

    waiting_for_next_chunk = asyncio.Event()

    class InterruptedUpload:
        filename = "recording.wav"

        def __init__(self):
            self.read_count = 0

        async def read(self, size):
            self.read_count += 1

            if self.read_count == 1:
                return WAV_DATA

            waiting_for_next_chunk.set()
            await asyncio.Event().wait()
            return b""

    audio = InterruptedUpload()
    task = asyncio.create_task(save_uploaded_audio(audio))

    try:
        await asyncio.wait_for(
            waiting_for_next_chunk.wait(),
            timeout=3,
        )

        assert len(list(tmp_path.iterdir())) == 1

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert list(tmp_path.iterdir()) == [], (
            "Partial audio file remained after cancellation"
        )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
