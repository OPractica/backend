import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

OUTLOOK = re.compile(r"@(outlook|hotmail|live|msn)\.[a-z.]{2,}$", re.I)
PHONE = re.compile(r"^\+?[0-9 ()-]{8,16}$")
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


def _phone(v: str) -> str:
    v = v.strip()
    if not PHONE.match(v):
        raise ValueError("Enter a valid phone number, e.g. +373 600 00000.")
    return v


class OutlookEmail(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _outlook(cls, v: str) -> str:
        v = v.strip().lower()
        if not OUTLOOK.search(v):
            raise ValueError("Use your Outlook email (outlook, hotmail or live).")
        return v


class RegisterIn(OutlookEmail):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str
    password: str = Field(min_length=6, max_length=64)
    _p = field_validator("phone")(_phone)


class ResendIn(OutlookEmail):
    pass


class VerifyIn(OutlookEmail):
    code: str = Field(pattern=r"^\d{6}$")


class LoginIn(OutlookEmail):
    password: str = Field(max_length=64)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SettingsPatch(BaseModel):
    theme: Literal["system", "light", "dark"] | None = None
    notify: bool | None = None


class UserPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    settings: SettingsPatch | None = None
    _p = field_validator("phone")(lambda v: v if v is None else _phone(v))


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    phone: str
    settings: dict
    created_at: datetime


class SeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    floor: int
    zone: str
    x: float
    y: float


class AvailOut(BaseModel):
    seat_id: str
    status: Literal["free", "busy", "mine"]
    booked_by: str | None = None
    booking_id: str | None = None


class BookingIn(BaseModel):
    seat_id: str
    date: date
    start: str = Field(default="09:00", pattern=HHMM)
    end: str = Field(default="18:00", pattern=HHMM)


class BookingOut(BaseModel):
    id: str
    seat_id: str
    seat_label: str
    date: str
    start: str
    end: str
    status: str
