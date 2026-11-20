import httpx
import ollama
from langchain_core.exceptions import ModelError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from app.core.config import settings

OLLAMA_NUM_CTX = 8192
OLLAMA_TIMEOUT_SECONDS = 180

# Ошибки «модель недоступна или сбоит». Не зависят от того, какой провайдер включён:
# облачная модель сообщает о них через ModelError, а локальный сервер Ollama
# через ошибки соединения (httpx) и ответа сервера (ollama).
MODEL_ERRORS: tuple[type[Exception], ...] = (
    ModelError,
    httpx.HTTPError,
    ollama.ResponseError,
)


class LLMNotConfiguredError(RuntimeError):
    """Не задан ключ модели в настройках."""


def get_llm() -> BaseChatModel:
    """Чат-модель по настройкам: LLM_PROVIDER=gemini (облако) или ollama (локальная)."""
    if settings.llm_provider == "ollama":
        # Локальная модель: «раздумья» выключены ради скорости, контекст задан явно
        # (по умолчанию у Ollama он всего 4096 токенов).
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_ctx=OLLAMA_NUM_CTX,
            reasoning=False,
            client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
        )
    # Gemini: температуру не задаём (для Gemini 3 рекомендовано значение по умолчанию 1.0,
    # при меньших модель может зацикливаться). thinking_level="low": меньше раздумий,
    # ответы быстрее и расходуют меньше лимита.
    if not settings.google_api_key:
        raise LLMNotConfiguredError(
            "GOOGLE_API_KEY is not set. Add it to .env (see .env.example)."
        )
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        api_key=settings.google_api_key,
        thinking_level="low",
        max_retries=2,
    )
