"""Проверка tools: что видит модель и как инструменты отвечают на реальной базе.

Запуск: uv run python -m scripts.check_ai_tools
"""

import asyncio

from app.ai.tools import make_tools
from app.core.db import engine

USER_ID = 1
START = "2026-12-01T09:00"
END = "2026-12-01T10:00"


async def main() -> None:
    tools = {tool.name: tool for tool in make_tools(USER_ID)}
    search, list_bookings = tools["search_free_seats"], tools["list_my_bookings"]

    print("=== Что видит модель ===")
    for tool in tools.values():
        print(f"\n{tool.name}")
        print(f"Описание: {tool.description}")
        print(f"Аргументы: {list(tool.args)}")

    cases = [
        ("поиск: есть места", search, {"start": START, "end": END}),
        ("поиск: зона window", search, {"start": START, "end": END, "zone": "window"}),
        ("поиск: такой зоны нет", search, {"start": START, "end": END, "zone": "xyz"}),
        ("поиск: неверный формат времени", search, {"start": "завтра", "end": END}),
        ("поиск: конец раньше начала", search, {"start": END, "end": START}),
        ("мои брони", list_bookings, {}),
    ]
    print("\n=== Вызовы инструментов ===")
    for name, tool, args in cases:
        print(f"\n--- {name}")
        print(await tool.ainvoke(args))

    await engine.dispose()


asyncio.run(main())
