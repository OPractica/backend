"""Граф диалога на LangGraph.

Узлы: START -> detect_language -> agent -> confirm -> END.
Язык определяет код, подтверждение брони строит шаблон, а не модель.
"""

from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from app.ai.confirmation import confirmations_for
from app.ai.language import Language, dialog_language


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
    """Если за этот ход бронь создана или отменена, ответ строит шаблон, а не модель."""
    confirmations = confirmations_for(state["messages"], state["language"])
    if not confirmations:
        return {}
    answer = "\n".join(confirmations)
    # В историю кладём тот же текст, чтобы следующий ход видел именно его.
    return {"messages": [*state["messages"][:-1], AIMessage(answer)], "answer": answer}


def build_dialog_graph(agent_for: Callable[[Language], Any]):
    builder = StateGraph(DialogState)
    builder.add_node("detect_language", detect_language_node)
    builder.add_node("agent", make_agent_node(agent_for))
    builder.add_edge(START, "detect_language")
    builder.add_node("confirm", confirm_node)
    builder.add_edge("detect_language", "agent")
    builder.add_edge("agent", "confirm")
    builder.add_edge("confirm", END)
    return builder.compile()
