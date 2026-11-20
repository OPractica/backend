"""Единый вход в агента для API: история диалога по сессиям и вызов агента."""

from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage

from app.ai.agent import build_agent

# История диалогов в памяти процесса: (user_id, session_id) -> сообщения.
# Временное решение. В ключе есть user_id, поэтому
# пользователь не может подставить чужой session_id и увидеть чужой диалог.
# Сообщения хранятся целыми объектами: у ответов Gemini внутри есть служебные подписи.
_history: dict[tuple[int, str], list[BaseMessage]] = {}


async def run_chat(
    user_id: int, text: str, session_id: str | None = None
) -> tuple[str, str]:
    """Передать сообщение агенту от имени пользователя. Вернуть (ответ, session_id)."""
    session_id = session_id or uuid4().hex
    key = (user_id, session_id)
    messages = [*_history.get(key, []), HumanMessage(content=text)]
    agent = build_agent(user_id)
    result = await agent.ainvoke({"messages": messages})
    _history[key] = result["messages"]
    return result["messages"][-1].text, session_id
