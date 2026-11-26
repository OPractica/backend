"""Граф диалога на LangGraph.

START -> detect_language -> развилка:
  - ждали «да/нет» и получили «да»  -> cancel  -> END (отмену выполняет код)
  - ждали «да/нет» и получили «нет» -> keep    -> END
  - всё остальное                   -> agent -> confirm -> END
Язык, подтверждения и отмену определяет код, модель понимает просьбу человека.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from app.ai.confirmation import cancel_requests_for, confirmations_for
from app.ai.language import Language, dialog_language
from app.ai.messages import (
    AFTER_CANCEL,
    ANSWER_HINTS,
    KEPT,
    booking_cancelled,
    cancel_failed,
    room_cancelled,
)
from app.ai.pending import (
    PENDING_KEY,
    PendingCancel,
    pending_from_history,
    read_reply,
)

# Выполняет подтверждённые отмены и возвращает успех по каждой
Canceller = Callable[[list[PendingCancel]], Awaitable[list[bool]]]


class DialogState(TypedDict, total=False):
    messages: list[BaseMessage]  # вся история диалога, включая новое сообщение
    text: str  # последнее сообщение пользователя
    language_hint: Language | None  # язык, который передал клиент (например, из голоса)
    language: Language  # итоговый язык диалога, определён кодом
    answer: str  # ответ пользователю


def detect_language_node(state: DialogState) -> DialogState:
    """Определить язык кодом: подсказка клиента, иначе последнее понятное сообщение.

    Короткое «да» или «7-A03» не переключает язык: берётся язык предыдущих реплик.
    """
    user_texts = [
        m.text for m in reversed(state["messages"]) if isinstance(m, HumanMessage)
    ]
    return {"language": dialog_language(user_texts, hint=state.get("language_hint"))}


def route_reply(state: DialogState) -> Literal["cancel", "keep", "agent"]:
    """Развилка: это ответ на вопрос об отмене или обычное сообщение."""
    if pending_from_history(state["messages"]):
        reply = read_reply(state["messages"][-1].text)
        if reply == "yes":
            return "cancel"
        if reply == "no":
            return "keep"
    return "agent"


def _reply(state: DialogState, answer: str) -> DialogState:
    return {"messages": [*state["messages"], AIMessage(answer)], "answer": answer}


def make_cancel_node(cancel: Canceller):
    """Узел отмены: модель здесь не участвует."""

    async def cancel_node(state: DialogState) -> DialogState:
        language = state["language"]
        actions = pending_from_history(state["messages"])
        lines = []
        for action, done in zip(actions, await cancel(actions), strict=True):
            template = booking_cancelled if action["kind"] == "seat" else room_cancelled
            lines.append((template if done else cancel_failed)(language, action["id"]))
        lines.append(AFTER_CANCEL[language])
        return _reply(state, "\n".join(lines))

    return cancel_node


def keep_node(state: DialogState) -> DialogState:
    return _reply(state, KEPT[state["language"]])


def make_agent_node(agent_for: Callable[[Language], Any]):
    """Узел, который запускает агента (модель + инструменты) на истории диалога.

    Агента собираем уже после определения языка: язык ответа входит в его инструкцию.
    """

    async def agent_node(state: DialogState) -> DialogState:
        agent = agent_for(state["language"])
        result = await agent.ainvoke({"messages": state["messages"]})
        messages = result["messages"]
        return {"messages": messages, "answer": messages[-1].text}

    return agent_node


def confirm_node(state: DialogState) -> DialogState:
    """Если за этот ход что-то сделано или нужна отмена, ответ строит шаблон, а не модель."""
    language = state["language"]
    confirmations = confirmations_for(state["messages"], language)
    pending, questions = cancel_requests_for(state["messages"], language)
    if not confirmations and not pending:
        return {}
    lines = [*confirmations, *questions]
    extra = {}
    if pending:
        lines.append(ANSWER_HINTS[language])
        extra[PENDING_KEY] = pending
    answer = "\n".join(lines)
    # В историю кладём тот же текст, чтобы следующий ход видел именно его.
    message = AIMessage(answer, additional_kwargs=extra)
    return {"messages": [*state["messages"][:-1], message], "answer": answer}


def build_dialog_graph(agent_for: Callable[[Language], Any], cancel: Canceller):
    builder = StateGraph(DialogState)
    builder.add_node("detect_language", detect_language_node)
    builder.add_node("cancel", make_cancel_node(cancel))
    builder.add_node("keep", keep_node)
    builder.add_node("agent", make_agent_node(agent_for))
    builder.add_node("confirm", confirm_node)
    builder.add_edge(START, "detect_language")
    builder.add_conditional_edges("detect_language", route_reply)
    builder.add_edge("cancel", END)
    builder.add_edge("keep", END)
    builder.add_edge("agent", "confirm")
    builder.add_edge("confirm", END)
    return builder.compile()
