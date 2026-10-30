"""Консольный чат с агентом бронирования (для разработки).

Запуск: uv run python -m scripts.chat_cli
С показом вызовов инструментов: uv run python -m scripts.chat_cli --trace
Выход: пустая строка или exit.
"""

import asyncio
import sys

from langchain_core.exceptions import ModelError

from app.ai.agent import build_agent
from app.core.db import engine

USER_ID = 1  # тестовый пользователь из scripts.dev_reset_db


def print_trace(messages: list) -> None:
    """Показать, что агент делал внутри: какие инструменты вызывал и что получил."""
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            print(f"  [вызов] {call['name']}({call['args']})")
        if type(message).__name__ == "ToolMessage":
            print(f"  [результат] {str(message.content)[:200]}")


async def main(trace: bool) -> None:
    agent = build_agent(USER_ID)
    messages: list = []
    print("Ассистент бронирования. Для выхода: пустая строка или exit.")
    while True:
        text = input("Вы: ").strip()
        if text in {"", "exit", "quit"}:
            break
        known = len(messages)
        messages.append({"role": "user", "content": text})
        try:
            result = await agent.ainvoke({"messages": messages})
        except ModelError as error:
            # Любая ошибка модели (лимит, сеть, ключ) независимо от провайдера
            messages.pop()
            print(f"Ошибка при обращении к модели: {type(error).__name__}\n")
            continue
        messages = result["messages"]
        if trace:
            print_trace(messages[known:])
        print(f"Ассистент: {messages[-1].text}\n")
    await engine.dispose()


asyncio.run(main(trace="--trace" in sys.argv))
