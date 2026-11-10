from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import base

RETENTION_PERIOD = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(UTC)


def expiration_time() -> datetime:
    return utc_now() + RETENTION_PERIOD


class VoiceRecord(base):
    __tablename__ = "voice_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    audio_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    transcription: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=expiration_time,
        nullable=False,
        index=True,
    )
