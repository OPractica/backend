from datetime import UTC, datetime, timedelta

from database import base
from sqlalchemy import Column, DateTime, Integer, String, Text


class VoiceRecord(base):
    __tablename__ = "voice_records"

    id = Column(Integer, primary_key=True)
    audio_path = Column(String(500), nullable=False)
    transcription = Column(Text, nullable=False)
    language = Column(String(10), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(UTC) + timedelta(hours=24),
    )
