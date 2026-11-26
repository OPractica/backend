"""Единый вход в агента для API: история диалога по сессиям и вызов графа."""

from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.ai.agent import build_agent
from app.ai.graph import build_dialog_graph
from app.ai.language import Language
from app.ai.memory import load_history, save_history
from app.ai.tools import cancel_confirmed


async def run_chat(
    user_id: int,
    text: str,
    session_id: str | None = None,
    language: Language | None = None,
) -> tuple[str, str]:
    """Передать сообщение агенту от имени пользователя. Вернуть (ответ, session_id).

    История хранится в базе (app/ai/memory.py) и привязана к паре (user_id, session_id):
    пользователь не может подставить чужой session_id и увидеть чужой диалог.
    Сообщения хранятся целыми объектами: у ответов Gemini внутри есть служебные подписи.
    """
    session_id = session_id or uuid4().hex
    messages = [*await load_history(user_id, session_id), HumanMessage(content=text)]
    graph = build_dialog_graph(
        lambda language: build_agent(user_id, language=language, confirm_cancel=True),
        lambda actions: cancel_confirmed(user_id, actions),
    )
    result = await graph.ainvoke(
        {"messages": messages, "text": text, "language_hint": language}
    )
    await save_history(user_id, session_id, result["messages"])
    return result["answer"], session_id
