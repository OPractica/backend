"""Проверка сервиса бронирования. Ничего не сохраняет в базе (всё откатывается).

Запуск: uv run python -m scripts.check_booking_service
"""

import asyncio
from datetime import UTC, datetime

from app.core.db import SessionLocal, engine
from app.services.booking import (
    BookingError,
    cancel_booking,
    create_booking,
    find_free_seats,
    list_user_bookings,
)

USER, OTHER_USER = 1, 2
failed = 0


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 12, 1, hour, minute, tzinfo=UTC)


def check(name: str, ok: bool, details: str = "") -> None:
    global failed
    failed += 0 if ok else 1
    print(f"{'OK  ' if ok else 'FAIL'} {name} {details}")


async def raises(coro, part: str) -> bool:
    try:
        await coro
    except BookingError as error:
        return part in str(error)
    return False


async def main() -> None:
    async with SessionLocal() as session:
        free = await find_free_seats(session, at(9), at(10), "window")
        check(
            "1. свободных мест у окна: 4", len(free) == 4, str([s.label for s in free])
        )

        booking = await create_booking(session, USER, 1, at(9), at(10), source="ai")
        check(
            "2. бронь создана", booking.id is not None and booking.status == "confirmed"
        )
        check("2b. источник сохранён", booking.source == "ai")

        free = await find_free_seats(session, at(9), at(10), "window")
        check(
            "3. занятое место исчезло из поиска",
            [s.label for s in free] == ["7-A02", "7-A03", "7-A04"],
        )

        check(
            "4. повторная бронь на то же время отклонена",
            await raises(
                create_booking(session, USER, 1, at(9, 30), at(10, 30)), "занято"
            ),
        )

        second = await create_booking(session, USER, 1, at(10), at(11))
        check("5. соседний интервал 10-11 разрешён", second.id is not None)

        check(
            "6. конец раньше начала отклонён",
            await raises(create_booking(session, USER, 2, at(11), at(10)), "позже"),
        )
        check(
            "7. несуществующее место отклонено",
            await raises(
                create_booking(session, USER, 999, at(9), at(10)), "не найдено"
            ),
        )

        mine = await list_user_bookings(session, USER)
        check(
            "8. в списке 2 брони по порядку",
            [b.id for b in mine] == [booking.id, second.id],
        )

        check(
            "9. чужую бронь отменить нельзя",
            await raises(cancel_booking(session, OTHER_USER, booking.id), "не найдена"),
        )

        cancelled = await cancel_booking(session, USER, booking.id)
        check("10. свою бронь можно отменить", cancelled.status == "cancelled")
        check(
            "11. повторная отмена отклонена",
            await raises(cancel_booking(session, USER, booking.id), "уже отменена"),
        )

        free = await find_free_seats(session, at(9), at(10), "window")
        check(
            "12. после отмены место снова свободно", "7-A01" in [s.label for s in free]
        )

        mine = await list_user_bookings(session, USER)
        check("13. в списке осталась 1 бронь", [b.id for b in mine] == [second.id])

        await session.rollback()
    await engine.dispose()
    print(
        "\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if failed == 0 else f"\nПровалено проверок: {failed}"
    )


asyncio.run(main())
