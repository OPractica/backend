from pathlib import Path

from app.services.preferences.parser import extract_preferences
from app.services.voice.transcribe import transcribe_audio_with_language


def process_voice_preferences(
    file_path: str | Path,
    language: str | None = "auto",
) -> dict[str, object]:
    """Transcribe audio and extract multilingual seat preferences.

    Args:
        file_path: Path to the audio recording.
        language: "auto", "ru", "ro", "en", or None.

    Returns:
        Transcription, resolved language, extracted attributes,
        and preferences requiring clarification.
    """
    transcription = transcribe_audio_with_language(
        file_path,
        language,
    )

    preferences = extract_preferences(
        transcription.text,
        transcription.language,
    )

    return {
        "transcription": transcription.text,
        "language": preferences["language"],
        "attributes": preferences["attributes"],
        "needs_clarification": preferences["needs_clarification"],
    }
