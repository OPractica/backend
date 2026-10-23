"""Инструменты (tools) агента."""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, tool

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.booking import (
    BookingError,
    cancel_booking,
    create_booking,
    find_free_seats,
    list_user_bookings,
)

OFFICE_TZ = ZoneInfo(settings.office_timezone)


def _parse_local(value: str) -> datetime:
    """'2026-10-16T09:00' (местное время офиса) -> datetime с часовым поясом."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise BookingError(
            f"Не удалось понять время '{value}'. Нужен формат ГГГГ-ММ-ДДTЧЧ:ММ."
        ) from None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=OFFICE_TZ)
    return parsed.astimezone(OFFICE_TZ)


def _parse_interval(start: str, end: str) -> tuple[datetime, datetime]:
    starts_at, ends_at = _parse_local(start), _parse_local(end)
    if ends_at <= starts_at:
        raise BookingError("Время окончания должно быть позже времени начала.")
    return starts_at, ends_at


def _fmt(moment: datetime) -> str:
    return moment.astimezone(OFFICE_TZ).strftime("%Y-%m-%d %H:%M")


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
        Возвращает список мест: id, название, зона и свойства (window, quiet, monitors, dock).
        """
        try:
            starts_at, ends_at = _parse_interval(start, end)
            async with SessionLocal() as session:
                seats = await find_free_seats(session, starts_at, ends_at, zone or None)
        except BookingError as error:
            return f"Ошибка: {error}"
        if not seats:
            return "Свободных мест на это время нет."
        return "\n".join(
            f"id={seat.id} место={seat.label} зона={seat.zone} свойства={seat.attributes}"
            for seat in seats
        )

    @tool
    async def list_my_bookings() -> str:
        """Показать будущие подтверждённые брони текущего пользователя."""
        async with SessionLocal() as session:
            bookings = await list_user_bookings(session, user_id)
        if not bookings:
            return "У пользователя нет активных броней."
        return "\n".join(
            f"бронь {b.id}: место id={b.seat_id}, {_fmt(b.starts_at)} - {_fmt(b.ends_at)}"
            for b in bookings
        )

    @tool
    async def book_seat(seat_id: int, start: str, end: str) -> str:
        """Забронировать конкретное место для текущего пользователя.

        seat_id: id места из результата search_free_seats (не придумывай id).
        start: начало, формат ГГГГ-ММ-ДДTЧЧ:ММ, местное время.
        end: конец в том же формате.
        """
        try:
            starts_at, ends_at = _parse_interval(start, end)
            async with SessionLocal() as session:
                booking = await create_booking(
                    session, user_id, seat_id, starts_at, ends_at, source="ai"
                )
                await session.commit()
                return (
                    f"Бронь создана: номер брони {booking.id}, место id={seat_id}, "
                    f"с {_fmt(booking.starts_at)} до {_fmt(booking.ends_at)}."
                )
        except BookingError as error:
            return f"Ошибка: {error}"

    @tool
    async def cancel_my_booking(booking_id: int) -> str:
        """Отменить бронь текущего пользователя по номеру брони.

        booking_id: номер брони из list_my_bookings или из подтверждения брони.
        """
        try:
            async with SessionLocal() as session:
                booking = await cancel_booking(session, user_id, booking_id)
                await session.commit()
                return f"Бронь {booking.id} отменена."
        except BookingError as error:
            return f"Ошибка: {error}"

    return [search_free_seats, book_seat, cancel_my_booking, list_my_bookings]
