"""Инструменты (tools) агента."""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, tool

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.database import Seat
from app.services.booking import (
    BookingError,
    cancel_booking,
    create_booking,
    find_free_seats,
    get_seat_by_label,
    list_user_bookings,
)

OFFICE_TZ = ZoneInfo(settings.office_timezone)


def _parse_local(value: str) -> datetime:
    """'2026-10-16T09:00' (местное время офиса) -> datetime с часовым поясом."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise BookingError(
            f"Could not read the time '{value}'.", "invalid_time_format"
        ) from None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=OFFICE_TZ)
    return parsed.astimezone(OFFICE_TZ)


def _parse_interval(start: str, end: str) -> tuple[datetime, datetime]:
    starts_at, ends_at = _parse_local(start), _parse_local(end)
    if ends_at <= starts_at:
        raise BookingError(
            "The end time must be later than the start time.", "invalid_time_range"
        )
    return starts_at, ends_at


def _fmt(moment: datetime) -> str:
    return moment.astimezone(OFFICE_TZ).strftime("%Y-%m-%d %H:%M")


def _error_hint(code: str) -> str | None:
    """Короткое английское пояснение к коду ошибки сервиса (язык ответа выберет модель)."""
    hints = {
        "invalid_time_format": "the time must look like YYYY-MM-DDTHH:MM",
        "invalid_time_range": "the end time must be later than the start time",
        "seat_not_found": "no such seat, or it is not available",
        "seat_label_ambiguous": "the seat name matches several seats",
        "seat_already_booked": "the seat is already booked for this time",
        "user_booking_overlap": "the user already has a booking for this time",
        "booking_not_found": "there is no such booking",
        "booking_already_cancelled": "the booking is already cancelled",
        "booking_in_past": "bookings in the past are not allowed",
        "booking_spans_days": "a booking must start and end on the same day",
        "office_closed_weekend": "the office is closed on weekends",
        "outside_office_hours": (
            "outside office hours "
            f"({settings.office_open_hour:02d}:00-{settings.office_close_hour:02d}:00)"
        ),
        "booking_too_long": f"a booking cannot be longer than {settings.booking_max_hours} hours",
        "booking_too_short": f"a booking cannot be shorter than {settings.booking_min_minutes} minutes",
    }
    return hints.get(code)


def _error_text(error: BookingError) -> str:
    """Ответ инструмента об ошибке: код и пояснение на английском."""
    return f"error {error.code}: {_error_hint(error.code) or error}"


def make_tools(user_id: int) -> list[BaseTool]:
    """Собрать инструменты для конкретного пользователя.

    user_id зашит в инструменты: модель не может бронировать или отменять за других.
    """

    @tool
    async def search_free_seats(start: str, end: str, zone: str = "") -> str:
        """Найти свободные места в офисе на интервал времени.

        start: начало, местное время, формат ГГГГ-ММ-ДДTЧЧ:ММ (например 2026-10-16T09:00).
        end: конец в том же формате.
        zone: необязательно. Передавай, только если пользователь прямо назвал зону офиса
        (window, quiet, open или cozy). Для пожеланий вроде «у окна» или «тихое» зону не передавай:
        такие места могут быть в любой зоне, смотри их свойства в ответе.
        Возвращает список мест: название (например 7-A03), зона и свойства (window, quiet, monitors, dock).
        """
        try:
            starts_at, ends_at = _parse_interval(start, end)
            async with SessionLocal() as session:
                seats = await find_free_seats(session, starts_at, ends_at, zone or None)
        except BookingError as error:
            return _error_text(error)
        if not seats:
            return "no free seats for this time"
        return "\n".join(
            f"seat={seat.label} zone={seat.zone} properties={seat.attributes}"
            for seat in seats
        )

    @tool
    async def list_my_bookings() -> str:
        """Показать будущие подтверждённые брони текущего пользователя."""
        async with SessionLocal() as session:
            bookings = await list_user_bookings(session, user_id)
            labels = {}
            for booking in bookings:
                seat = await session.get(Seat, booking.seat_id)
                labels[booking.id] = seat.label if seat else "?"
        if not bookings:
            return "the user has no active bookings"
        return "\n".join(
            f"booking {b.id}: seat {labels[b.id]}, {_fmt(b.starts_at)} - {_fmt(b.ends_at)}"
            for b in bookings
        )

    @tool
    async def book_seat(seat: str, start: str, end: str) -> str:
        """Забронировать конкретное место для текущего пользователя.

        seat: название места, например 7-A03. Бери его из результата search_free_seats
        или из слов пользователя, ничего не придумывай.
        start: начало, формат ГГГГ-ММ-ДДTЧЧ:ММ, местное время.
        end: конец в том же формате.
        """
        try:
            starts_at, ends_at = _parse_interval(start, end)
            async with SessionLocal() as session:
                found = await get_seat_by_label(session, seat)
                booking = await create_booking(
                    session, user_id, found.id, starts_at, ends_at, source="ai"
                )
                await session.commit()
                return (
                    f"booking created: booking id {booking.id}, seat {found.label}, "
                    f"from {_fmt(booking.starts_at)} to {_fmt(booking.ends_at)}"
                )
        except BookingError as error:
            return _error_text(error)

    @tool
    async def cancel_my_booking(booking_id: int) -> str:
        """Отменить бронь текущего пользователя по номеру брони.

        booking_id: номер брони из list_my_bookings или из подтверждения брони.
        """
        try:
            async with SessionLocal() as session:
                booking = await cancel_booking(session, user_id, booking_id)
                await session.commit()
                return f"booking {booking.id} cancelled"
        except BookingError as error:
            return _error_text(error)

    return [search_free_seats, book_seat, cancel_my_booking, list_my_bookings]
