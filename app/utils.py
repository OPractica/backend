from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.office_tz)


def utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def now() -> datetime:
    return datetime.now(UTC)
