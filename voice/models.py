
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from database import base


class VoiceRecord(base):
    __tablename__ = "voice_records"

    id = Column(Integer, primary_key=True)
    audio_path = Column(String(500), nullable=False)
    transcription = Column(Text, nullable=False)
    language = Column(String(10), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc)
        + timedelta(hours=24),
    )
