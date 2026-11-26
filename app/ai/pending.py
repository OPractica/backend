"""Отмена с подтверждением: какие отмены ждут ответа и что ответил пользователь.

Модель только запрашивает отмену. Список ожидающих действий хранится в истории
диалога на сервере, а ответ «да» или «нет» читает код, а не модель.
"""

import re
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage

PENDING_KEY = "pending_cancel"  # поле в additional_kwargs сообщения с вопросом
MAX_REPLY_WORDS = 6  # длиннее это уже не «да/нет», а новая просьба


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


YES_WORDS = _words(
    """да ага угу конечно подтверждаю отмени отменить отменяй отмените отменяйте
    хорошо ок окей yes yeah yep sure confirm ok okay cancel
    da desigur sigur confirm bine anulează anuleaza anulați anulati"""
)
NO_WORDS = _words(
    """нет не неа оставь оставить оставьте стоп передумал передумала
    no nope not dont keep stop nu păstrează pastreaza"""
)
FILLER_WORDS = _words(
    """пожалуйста спасибо ее её их эту все всё бронь брони надо нужно
    please thanks thank you do it them the all booking bookings
    te rog mulțumesc multumesc o le toate anula rezervarea rezervările rezervarile"""
)


class PendingCancel(TypedDict):
    kind: Literal["seat", "room"]
    id: int


def read_reply(text: str) -> Literal["yes", "no"] | None:
    """Понять короткий ответ на вопрос об отмене. Всё неоднозначное это None.

    «Да» засчитывается, только если в сообщении нет ничего, кроме согласия:
    «да, но сначала покажи брони» не отменяет ничего.
    """
    words = re.findall(r"\w+", re.sub(r"['’]", "", text.casefold()))
    if not words or len(words) > MAX_REPLY_WORDS:
        return None
    if NO_WORDS.intersection(words):
        return "no" if set(words) <= NO_WORDS | YES_WORDS | FILLER_WORDS else None
    if YES_WORDS.intersection(words) and set(words) <= YES_WORDS | FILLER_WORDS:
        return "yes"
    return None


def pending_from_history(messages: list[BaseMessage]) -> list[PendingCancel]:
    """Отмены, о которых спросили прямо перед последним сообщением пользователя.

    Подтверждение действует только на следующий ответ: если разговор ушёл дальше,
    старый вопрос больше ничего не отменяет.
    """
    if len(messages) < 2 or not isinstance(messages[-2], AIMessage):
        return []
    return list(messages[-2].additional_kwargs.get(PENDING_KEY, []))
