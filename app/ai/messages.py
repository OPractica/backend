"""Готовые ответы на трёх языках. Критичные факты (место, дата, номер брони) подставляет код."""

from datetime import datetime

from app.ai.language import Language

REFUSALS: dict[Language, str] = {
    "ru": "Я помогаю только с бронированием рабочих мест и переговорных. Хотите что-нибудь забронировать?",
    "ro": "Vă pot ajuta doar cu rezervarea locurilor de muncă și a sălilor de ședință. Doriți să rezervați ceva?",
    "en": "I can only help with booking workspaces and meeting rooms. Would you like to book something?",
}


def refusal(language: Language) -> str:
    return REFUSALS[language]


def booking_confirmation(
    language: Language,
    seat: str,
    starts_at: datetime,
    ends_at: datetime,
    booking_id: int,
) -> str:
    day = starts_at.date().isoformat()
    start, end = starts_at.strftime("%H:%M"), ends_at.strftime("%H:%M")
    if language == "ru":
        return f"Место {seat} забронировано на {day} с {start} до {end}. Номер брони: {booking_id}."
    if language == "ro":
        return f"Locul {seat} a fost rezervat pentru {day}, între {start} și {end}. Numărul rezervării: {booking_id}."
    return f"Seat {seat} is booked for {day} from {start} to {end}. Booking number: {booking_id}."


def booking_cancelled(language: Language, booking_id: int) -> str:
    if language == "ru":
        return f"Бронь {booking_id} отменена."
    if language == "ro":
        return f"Rezervarea {booking_id} a fost anulată."
    return f"Booking {booking_id} is cancelled."


def room_confirmation(
    language: Language,
    room: str,
    starts_at: datetime,
    ends_at: datetime,
    booking_id: int,
) -> str:
    day = starts_at.date().isoformat()
    start, end = starts_at.strftime("%H:%M"), ends_at.strftime("%H:%M")
    if language == "ru":
        return f"Переговорная {room} забронирована на {day} с {start} до {end}. Номер брони: {booking_id}."
    if language == "ro":
        return f"{room} a fost rezervată pentru {day}, între {start} și {end}. Numărul rezervării: {booking_id}."
    return f"Meeting room {room} is booked for {day} from {start} to {end}. Booking number: {booking_id}."


def room_cancelled(language: Language, booking_id: int) -> str:
    if language == "ru":
        return f"Бронь переговорной {booking_id} отменена."
    if language == "ro":
        return f"Rezervarea sălii {booking_id} a fost anulată."
    return f"Meeting room booking {booking_id} is cancelled."
