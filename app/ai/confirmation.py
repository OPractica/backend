"""Подтверждения для успешных действий: текст собирает код, а не модель.

Модель иногда отвечает не на том языке или путает дату. Поэтому после запуска
агента мы смотрим на результаты инструментов (book_seat, cancel_my_booking)
и, если действие выполнено, строим подтверждение по шаблону на языке диалога.
Если действий не было (поиск, вопрос, уточнение), остаётся ответ модели.
"""

import re
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

from app.ai.language import Language
from app.ai.messages import booking_cancelled, booking_confirmation

# Формат результатов инструментов задан в app/ai/tools.py (book_seat, cancel_my_booking).
BOOKED = re.compile(
    r"^booking created: booking id (?P<id>\d+), seat (?P<seat>[^,\s]+), "
    r"from (?P<start>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) to (?P<end>\d{4}-\d{2}-\d{2} \d{2}:\d{2})$"
)
CANCELLED = re.compile(r"^booking (?P<id>\d+) cancelled$")
TIME_FORMAT = "%Y-%m-%d %H:%M"


def messages_of_this_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Сообщения после последней реплики пользователя."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return list(messages)


def confirmations_for(messages: list[BaseMessage], language: Language) -> list[str]:
    """Подтверждения всех выполненных за этот ход действий, в порядке выполнения."""
    texts = []
    for message in messages_of_this_turn(messages):
        if not isinstance(message, ToolMessage):
            continue
        content = message.text.strip()
        if message.name == "book_seat" and (found := BOOKED.match(content)):
            texts.append(
                booking_confirmation(
                    language,
                    found["seat"],
                    datetime.strptime(found["start"], TIME_FORMAT),
                    datetime.strptime(found["end"], TIME_FORMAT),
                    int(found["id"]),
                )
            )
        elif message.name == "cancel_my_booking" and (
            found := CANCELLED.match(content)
        ):
            texts.append(booking_cancelled(language, int(found["id"])))
    return texts
