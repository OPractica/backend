
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import base
from voice.models import VoiceRecord

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "audio_storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://office:office@localhost:5432/office_booking",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_voice_database():
    VoiceRecord.__table__.create(
        bind=engine,
        checkfirst=True,
    )


def save_voice_record(
    audio_path: Path,
    text: str,
    language: str,
) -> VoiceRecord:
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        record = VoiceRecord(
            audio_path=audio_path.name,
            transcription=text,
            language=language,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def delete_expired_records() -> int:
    now = datetime.now(timezone.utc)
    deleted_count = 0

    with Session(engine) as session:
        records = session.scalars(
            select(VoiceRecord).where(
                VoiceRecord.expires_at <= now
            )
        ).all()

        for record in records:
            # Only UUID-named files in our storage directory.
            name = Path(record.audio_path).name
            if name != record.audio_path:
                continue

            file_path = STORAGE_DIR / name

            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                # Keep the record for a later cleanup attempt.
                continue

            session.delete(record)
            deleted_count += 1

        session.commit()

    return deleted_count
