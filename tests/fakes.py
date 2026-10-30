from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Фейковая модель для тестов: отвечает заранее заданными сообщениями по порядку.

    Запоминает, какие сообщения получала на каждом шаге, чтобы тест мог их проверить.
    """

    responses: list[AIMessage]
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        # Настоящая модель получает здесь описания инструментов, фейку они не нужны
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        message = self.responses[len(self.seen) - 1]
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    """Сообщение, в котором модель просит вызвать инструмент."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )
