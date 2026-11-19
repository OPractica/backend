from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.services.voice.storage import STORAGE_DIR

MAX_AUDIO_BYTES = 24_000_000
CHUNK_SIZE = 1024 * 1024

SUPPORTED_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".ogg",
    ".wav",
    ".webm",
}


class InvalidAudioError(ValueError):
    """The uploaded file is empty, invalid, or unsupported."""


class AudioTooLargeError(ValueError):
    """The uploaded audio exceeds the configured size limit."""


def _has_audio_signature(suffix: str, header: bytes) -> bool:
    """Check recognizable audio container signatures."""
    if suffix == ".wav":
        return header.startswith(b"RIFF") and header[8:12] == b"WAVE"

    if suffix == ".flac":
        return header.startswith(b"fLaC")

    if suffix == ".ogg":
        return header.startswith(b"OggS")

    if suffix == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")

    if suffix in {".mp4", ".m4a"}:
        return header[4:8] == b"ftyp"

    if suffix in {".mp3", ".mpeg", ".mpga"}:
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
        )

    return False


async def save_uploaded_audio(file: UploadFile) -> Path:
    """Validate and store uploaded audio with a random filename."""
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise InvalidAudioError("Unsupported audio format")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = STORAGE_DIR / f"{uuid4().hex}{suffix}"

    total_size = 0
    header = b""

    try:
        with audio_path.open("xb") as destination:
            while chunk := await file.read(CHUNK_SIZE):
                total_size += len(chunk)

                if total_size > MAX_AUDIO_BYTES:
                    raise AudioTooLargeError("Audio file exceeds the 24 MB limit")

                if len(header) < 16:
                    header += chunk[: 16 - len(header)]

                destination.write(chunk)

        if total_size == 0:
            raise InvalidAudioError("Audio file is empty")

        if not _has_audio_signature(suffix, header):
            raise InvalidAudioError(
                "File content does not match a supported audio format"
            )

        return audio_path

    except BaseException:
        with suppress(OSError):
            audio_path.unlink(missing_ok=True)
        raise
