from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.voice import transcribe


@pytest.fixture
def fake_groq(monkeypatch):
    client = MagicMock()
    constructor = MagicMock(return_value=client)

    monkeypatch.setattr(transcribe, "Groq", constructor)

    return client, constructor


@pytest.mark.parametrize(
    ("language", "expected_text"),
    [
        ("ru", "Тихое место у окна"),
        ("ro", "Loc liniștit lângă fereastră"),
        ("en", "Quiet desk near the window"),
    ],
)
def test_transcription_supported_languages(
    tmp_path, fake_groq, language, expected_text
):
    client, constructor = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text=expected_text
    )

    result = transcribe.transcribe_audio(audio, language)

    assert result == expected_text

    constructor.assert_called_once_with(api_key=transcribe.settings.groq_api_key)

    options = client.audio.transcriptions.create.call_args.kwargs

    assert options["model"] == transcribe.WHISPER_MODEL
    assert options["language"] == language
    assert options["response_format"] == "json"


def test_automatic_language_detection(tmp_path, fake_groq):
    client, _ = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    client.audio.transcriptions.create.return_value = SimpleNamespace(text="Hello")

    result = transcribe.transcribe_audio(audio)

    options = client.audio.transcriptions.create.call_args.kwargs

    assert result == "Hello"
    assert "language" not in options


def test_unsupported_language(tmp_path, fake_groq):
    _, constructor = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    with pytest.raises(ValueError, match="Unsupported language"):
        transcribe.transcribe_audio(audio, "fr")

    constructor.assert_not_called()


def test_missing_audio_file(tmp_path, fake_groq):
    _, constructor = fake_groq

    with pytest.raises(FileNotFoundError):
        transcribe.transcribe_audio(tmp_path / "missing.wav")

    constructor.assert_not_called()


def test_empty_audio_file(tmp_path, fake_groq):
    _, constructor = fake_groq

    audio = tmp_path / "empty.wav"
    audio.write_bytes(b"")

    with pytest.raises(ValueError, match="Audio file is empty"):
        transcribe.transcribe_audio(audio)

    constructor.assert_not_called()


def test_transcription_removes_whitespace(tmp_path, fake_groq):
    client, _ = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="  Hello world  "
    )

    assert transcribe.transcribe_audio(audio, "en") == "Hello world"


def test_empty_transcription(tmp_path, fake_groq):
    client, _ = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    client.audio.transcriptions.create.return_value = SimpleNamespace(text="   ")

    with pytest.raises(ValueError, match="Transcription is empty"):
        transcribe.transcribe_audio(audio, "en")


def test_groq_api_failure(tmp_path, fake_groq):
    client, _ = fake_groq

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake audio content")

    client.audio.transcriptions.create.side_effect = RuntimeError(
        "Groq service unavailable"
    )

    with pytest.raises(RuntimeError, match="Groq service unavailable"):
        transcribe.transcribe_audio(audio, "en")
