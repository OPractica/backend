"""Граф диалога на LangGraph."""

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph

from app.ai.language import Language, detect_language


class DialogState(TypedDict, total=False):
    messages: list[BaseMessage]  # вся история диалога, включая новое сообщение
    text: str  # последнее сообщение пользователя
    language_hint: Language | None  # язык, который передал клиент (например, из голоса)
    language: Language  # итоговый язык диалога, определён кодом
    answer: str  # ответ пользователю


def detect_language_node(state: DialogState) -> DialogState:
    """Определить язык кодом: подсказка клиента важнее угадывания по тексту."""
    return {"language": detect_language(state["text"], hint=state.get("language_hint"))}


def make_agent_node(agent: Any):
    """Узел, который запускает агента (модель + инструменты) на истории диалога."""

    async def agent_node(state: DialogState) -> DialogState:
        result = await agent.ainvoke({"messages": state["messages"]})
        messages = result["messages"]
        return {"messages": messages, "answer": messages[-1].text}

    return agent_node


def build_dialog_graph(agent: Any):
    builder = StateGraph(DialogState)
    builder.add_node("detect_language", detect_language_node)
    builder.add_node("agent", make_agent_node(agent))
    builder.add_edge(START, "detect_language")
    builder.add_edge("detect_language", "agent")
    builder.add_edge("agent", END)
    return builder.compile()
