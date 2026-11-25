import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.ai.graph import build_dialog_graph

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeAgent:
    """Агент-заглушка: запоминает, что получил, и отвечает фиксированным текстом."""

    def __init__(self, reply: str = "ok"):
        self.reply = reply
        self.seen: list[list] = []

    async def ainvoke(self, state: dict) -> dict:
        self.seen.append(state["messages"])
        return {"messages": [*state["messages"], AIMessage(self.reply)]}


async def run(agent, text, hint=None):
    graph = build_dialog_graph(lambda language: agent)
    return await graph.ainvoke(
        {"messages": [HumanMessage(text)], "text": text, "language_hint": hint}
    )


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Забронируй место на завтра", "ru"),
        ("Vreau un loc mâine", "ro"),
        ("Book me a seat tomorrow", "en"),
    ],
)
async def test_graph_detects_language_in_code(text, language):
    result = await run(FakeAgent(), text)
    assert result["language"] == language


async def test_graph_hint_from_client_wins_over_text():
    result = await run(FakeAgent(), "Забронируй место", hint="en")
    assert result["language"] == "en"


async def test_graph_returns_agent_answer_and_full_history():
    agent = FakeAgent("Место 7-A01 свободно")
    result = await run(agent, "Есть места?")
    assert result["answer"] == "Место 7-A01 свободно"
    assert [m.text for m in result["messages"]] == [
        "Есть места?",
        "Место 7-A01 свободно",
    ]


async def test_graph_passes_history_to_agent_unchanged():
    agent = FakeAgent()
    await run(agent, "Привет")
    assert len(agent.seen) == 1
    assert agent.seen[0][0].text == "Привет"
