"""Память диалогов ассистента: история сессий хранится в базе данных.

Раньше история лежала в памяти процесса и пропадала, когда сервер засыпал или
перезапускался (на бесплатном Render это происходит часто). Теперь она в таблице
ai_chat_sessions. Если база временно недоступна, ассистент не падает: он работает
с копией в памяти процесса, как раньше.
"""

import logging
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    messages_from_dict,
    messages_to_dict,
)
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import SessionLocal
from app.models.chat import ChatSession

logger = logging.getLogger(__name__)

MAX_MESSAGES = 60  # хвост истории, который передаём модели
RETENTION = timedelta(days=7)  # диалоги старше недели удаляются
MAX_FALLBACK_SESSIONS = 200

# Копия в памяти процесса: запасной вариант на случай сбоя базы.
_fallback: OrderedDict[tuple[int, str], list[BaseMessage]] = OrderedDict()


def trim_history(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Оставить последние MAX_MESSAGES сообщений, начиная с реплики пользователя.

    Нельзя обрезать посреди пары «вызов инструмента — результат»: модель такое отвергает.
    Поэтому хвост всегда начинается с сообщения пользователя.
    """
    if len(messages) <= MAX_MESSAGES:
        return messages
    for index in range(len(messages) - MAX_MESSAGES, len(messages)):
        if isinstance(messages[index], HumanMessage):
            return messages[index:]
    return messages[-1:]


def _remember(key: tuple[int, str], messages: list[BaseMessage]) -> None:
    _fallback[key] = messages
    _fallback.move_to_end(key)
    while len(_fallback) > MAX_FALLBACK_SESSIONS:
        _fallback.popitem(last=False)


async def load_history(user_id: int, session_id: str) -> list[BaseMessage]:
    """История сессии. Чужая сессия недоступна: ключ включает user_id."""
    key = (user_id, session_id)
    try:
        async with SessionLocal() as db:
            stored = await db.scalar(
                select(ChatSession.messages).where(
                    ChatSession.user_id == user_id, ChatSession.session_id == session_id
                )
            )
        if stored is not None:
            return messages_from_dict(stored)
    except (SQLAlchemyError, ValueError, KeyError, TypeError):
        logger.exception("Could not load the chat history from the database")
    return list(_fallback.get(key, []))


async def save_history(
    user_id: int, session_id: str, messages: list[BaseMessage]
) -> None:
    """Сохранить историю и заодно удалить старые диалоги этого пользователя."""
    messages = trim_history(messages)
    _remember((user_id, session_id), messages)
    try:
        payload = messages_to_dict(messages)
        async with SessionLocal() as db:
            await db.execute(
                delete(ChatSession).where(
                    ChatSession.user_id == user_id,
                    ChatSession.updated_at < datetime.now(UTC) - RETENTION,
                )
            )
            statement = insert(ChatSession).values(
                user_id=user_id, session_id=session_id, messages=payload
            )
            await db.execute(
                statement.on_conflict_do_update(
                    constraint="uq_ai_chat_sessions_user_session",
                    set_={"messages": payload, "updated_at": datetime.now(UTC)},
                )
            )
            await db.commit()
    except (SQLAlchemyError, ValueError, TypeError):
        logger.exception("Could not save the chat history to the database")
