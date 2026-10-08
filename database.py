from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

base = declarative_base()

class User(base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="employee")
    is_active = Column(Boolean, default=True) #Аккаунт активен?
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Seat(base):
    __tablename__ = 'seats'

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    floor = Column(Integer, nullable=False)
    zone = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    attributes = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Booking(base):
    __tablename__ = 'bookings'

    id = Column(Integer, primary_key=True, index=True)

    users_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    seats_id = Column(Integer, ForeignKey("seat.id", ondelete="CASCADE"), nullable=False)

    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)

    status = Column(String, default="confirmed", nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

