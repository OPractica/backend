from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SeatResponse(BaseModel):
    id: int
    label: str
    floor: int
    zone: str
    is_active: bool
    attributes: dict[str, Any] = {}
    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    seat_id: int
    starts_at: datetime
    ends_at: datetime
    source: str = "manual"


class BookingResponse(BaseModel):
    id: int
    user_id: int
    seat_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    source: str
    is_checked_in: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BookingUpdate(BaseModel):
    status: str | None = None
    is_checked_in: bool | None = None
