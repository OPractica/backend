from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.models.database import base


def utc_now():
    return datetime.now(UTC)


def expiration_time():
    return utc_now() + timedelta(hours=24)


class VoiceRecord(base):
    __tablename__ = "voice_records"

    id = Column(Integer, primary_key=True)

    audio_path = Column(
        String(500),
        nullable=False,
    )

    transcription = Column(
        Text,
        nullable=False,
    )

    language = Column(
        String(10),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at = Column(
        DateTime(timezone=True),
        default=expiration_time,
        nullable=False,
        index=True,
    )
