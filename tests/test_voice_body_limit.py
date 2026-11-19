import pytest

VOICE_URL = "/api/v1/voice/transcribe"
LIMIT = 25_000_000


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_voice_rejects_large_content_length(client):
    response = await client.post(
        VOICE_URL,
        content=b"",
        headers={
            "Content-Length": str(LIMIT + 1),
            "Content-Type": "multipart/form-data; boundary=voice104",
        },
    )

    assert response.status_code == 413


@pytest.mark.anyio
async def test_voice_rejects_stream_without_content_length(client):
    boundary = "voice104"

    async def audio_stream():
        yield (
            b"--voice104\r\n"
            b'Content-Disposition: form-data; name="file"; '
            b'filename="large.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n"
            b"RIFF\x00\x00\x00\x00WAVE"
        )

        chunk = b"\x00" * 1_000_000

        for _ in range(25):
            yield chunk

        yield b"\r\n--voice104--\r\n"

    request = client.build_request(
        "POST",
        VOICE_URL,
        headers={
            "Content-Type": (f"multipart/form-data; boundary={boundary}"),
        },
        content=audio_stream(),
    )

    assert "content-length" not in request.headers

    response = await client.send(request)

    assert response.status_code == 413
