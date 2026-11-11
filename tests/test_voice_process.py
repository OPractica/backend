from unittest.mock import MagicMock

import pytest

from app.services.voice import process
from app.services.voice.transcribe import TranscriptionResult


@pytest.mark.parametrize(
    ("language", "spoken_text", "expected_attributes"),
    [
        (
            "ru",
            "Хочу тихое место, но не у окна",
            {"quiet": True, "near_window": False},
        ),
        (
            "ro",
            "Vreau un loc liniștit, nu lângă geam",
            {"quiet": True, "near_window": False},
        ),
        (
            "en",
            "I want a quiet place, but not near the window",
            {"quiet": True, "near_window": False},
        ),
        (
            "en",
            "I don't want a docking station",
            {"docking_station": False},
        ),
        (
            "ru",
            "Не хочу два монитора",
            {},
        ),
    ],
)
def test_auto_language_voice_processing(
    monkeypatch,
    tmp_path,
    language,
    spoken_text,
    expected_attributes,
):
    audio_path = tmp_path / "sample.wav"

    fake_transcription = MagicMock(
        return_value=TranscriptionResult(
            text=spoken_text,
            language=language,
        )
    )

    monkeypatch.setattr(
        process,
        "transcribe_audio_with_language",
        fake_transcription,
    )

    result = process.process_voice_preferences(audio_path)

    assert result == {
        "transcription": spoken_text,
        "language": language,
        "attributes": expected_attributes,
        "needs_clarification": [],
    }

    fake_transcription.assert_called_once_with(audio_path, "auto")


@pytest.mark.parametrize(
    ("language", "spoken_text", "expected_attributes"),
    [
        (
            "ru",
            "Хочу место у окна",
            {"near_window": True},
        ),
        (
            "ro",
            "Vreau un loc lângă geam",
            {"near_window": True},
        ),
        (
            "en",
            "I want a quiet place",
            {"quiet": True},
        ),
    ],
)
def test_manual_language_voice_processing(
    monkeypatch,
    tmp_path,
    language,
    spoken_text,
    expected_attributes,
):
    audio_path = tmp_path / "sample.wav"

    fake_transcription = MagicMock(
        return_value=TranscriptionResult(
            text=spoken_text,
            language=language,
        )
    )

    monkeypatch.setattr(
        process,
        "transcribe_audio_with_language",
        fake_transcription,
    )

    result = process.process_voice_preferences(
        audio_path,
        language=language,
    )

    assert result["attributes"] == expected_attributes
    assert result["language"] == language

    fake_transcription.assert_called_once_with(
        audio_path,
        language,
    )


def test_voice_processing_needs_clarification(monkeypatch, tmp_path):
    fake_transcription = MagicMock(
        return_value=TranscriptionResult(
            text="Хочу уютное место",
            language="ru",
        )
    )

    monkeypatch.setattr(
        process,
        "transcribe_audio_with_language",
        fake_transcription,
    )

    result = process.process_voice_preferences(
        tmp_path / "sample.wav",
    )

    assert result["attributes"] == {}
    assert result["needs_clarification"] == ["cozy"]


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("Audio file not found"),
        ValueError("Transcription is empty"),
        RuntimeError("Groq service unavailable"),
    ],
)
def test_voice_processing_propagates_errors(
    monkeypatch,
    tmp_path,
    error,
):
    fake_transcription = MagicMock(side_effect=error)

    monkeypatch.setattr(
        process,
        "transcribe_audio_with_language",
        fake_transcription,
    )

    with pytest.raises(type(error), match=str(error)):
        process.process_voice_preferences(
            tmp_path / "sample.wav",
        )

    fake_transcription.assert_called_once()
