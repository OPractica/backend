from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

base = declarative_base()


class User(base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="employee")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Seat(base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    floor = Column(Integer, nullable=False)
    zone = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    attributes = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Booking(base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    seat_id = Column(
        Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False
    )

    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)

    status = Column(String, default="confirmed", nullable=False)
    source = Column(String, default="manual", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_checked_in = Column(
        Boolean, default=False, nullable=False
    )  # ?Подтвердил ли пользователь свое присутствие
