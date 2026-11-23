from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class ErrorResponse(BaseModel):
    detail: str
    code: str


class ValidationErrorItem(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    input: Any = None


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationErrorItem]
    code: str


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


class SeatAvailability(BaseModel):
    id: int
    label: str
    status: Literal["free", "booked"]


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


class RefreshRequest(BaseModel):
    refresh_token: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=64)
    language: Literal["ru", "ro", "en"] | None = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str


class MeetingRoomWithStatus(BaseModel):
    # Field names follow the meeting room API guide: roomId, roomEmail, ...
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    room_id: int
    room_email: str
    room_alias: str
    room_capacity: str
    room_equipments: str
    is_busy: bool


class MeetingRoomBookingCreate(BaseModel):
    room_id: int
    starts_at: datetime
    ends_at: datetime


class MeetingRoomBookingResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
