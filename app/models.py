import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.utils import now


def _id() -> str:
    return str(uuid.uuid4())


DEFAULT_SETTINGS = {"theme": "system", "notify": True}


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16), default="user")  # owner | admin | user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_SETTINGS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PendingSignup(Base):
    """Registration waits here. The real account is created only after the emailed code is confirmed."""

    __tablename__ = "pending_signups"
    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(100))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Seat(Base):
    __tablename__ = "seats"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # s1, s2 ... same ids as the SVG plan
    label: Mapped[str] = mapped_column(String(16))
    floor: Mapped[int] = mapped_column(Integer, default=7)
    zone: Mapped[str] = mapped_column(String(32), default="Orange kITchen")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    seat_id: Mapped[str] = mapped_column(ForeignKey("seats.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="confirmed")  # confirmed | cancelled
    source: Mapped[str] = mapped_column(String(12), default="manual")  # manual | voice
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
