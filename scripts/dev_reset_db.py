"""Локальная разработка: пересоздать таблицы и заполнить тестовыми данными.

ВНИМАНИЕ: удаляет все данные в базе из DATABASE_URL. Работает только с локальной базой
(localhost / 127.0.0.1), на другом хосте откажется.
Запуск: uv run python -m scripts.dev_reset_db
"""

import asyncio

from app.core.db import SessionLocal, engine
from app.models.database import Seat, User, base

SEATS = [
    {
        "label": "7-A01",
        "zone": "window",
        "attributes": {"window": True, "quiet": False, "monitors": 2, "dock": True},
    },
    {
        "label": "7-A02",
        "zone": "window",
        "attributes": {"window": True, "quiet": False, "monitors": 1, "dock": True},
    },
    {
        "label": "7-A03",
        "zone": "window",
        "attributes": {"window": True, "quiet": True, "monitors": 2, "dock": False},
    },
    {
        "label": "7-A04",
        "zone": "window",
        "attributes": {"window": True, "quiet": True, "monitors": 1, "dock": False},
    },
    {
        "label": "7-B01",
        "zone": "quiet",
        "attributes": {"window": False, "quiet": True, "monitors": 2, "dock": True},
    },
    {
        "label": "7-B02",
        "zone": "quiet",
        "attributes": {"window": False, "quiet": True, "monitors": 1, "dock": True},
    },
    {
        "label": "7-B03",
        "zone": "quiet",
        "attributes": {"window": False, "quiet": True, "monitors": 2, "dock": False},
    },
    {
        "label": "7-C01",
        "zone": "open",
        "attributes": {"window": False, "quiet": False, "monitors": 1, "dock": False},
    },
    {
        "label": "7-C02",
        "zone": "open",
        "attributes": {"window": False, "quiet": False, "monitors": 2, "dock": True},
    },
    {
        "label": "7-C03",
        "zone": "open",
        "attributes": {"window": False, "quiet": False, "monitors": 1, "dock": True},
    },
    {
        "label": "7-D01",
        "zone": "cozy",
        "attributes": {
            "window": True,
            "quiet": True,
            "monitors": 1,
            "dock": False,
            "cozy": True,
        },
    },
    {
        "label": "7-D02",
        "zone": "cozy",
        "attributes": {
            "window": False,
            "quiet": True,
            "monitors": 1,
            "dock": False,
            "cozy": True,
        },
    },
]


async def main() -> None:
    # Защита: стираем данные только в локальной базе.
    if engine.url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit(
            f"Отказ: база на хосте {engine.url.host!r} не локальная, ничего не удалено."
        )

    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.drop_all)
        await conn.run_sync(base.metadata.create_all)

    async with SessionLocal() as session:
        session.add(
            User(
                email="test.user@orange.local",
                password_hash="dev-only-not-a-real-hash",
                full_name="Test User",
            )
        )
        session.add_all([Seat(floor=7, **seat) for seat in SEATS])
        await session.commit()

    await engine.dispose()
    print(
        f"Готово: таблицы пересозданы, добавлено мест: {len(SEATS)}, пользователей: 1"
    )


asyncio.run(main())
