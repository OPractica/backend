from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


def get_llm() -> BaseChatModel:
    """
    температуру не задаем: значение по умолчанию (1.0),
    при меньших модель может зацикливаться.
    thinking_level="low": меньше раздумий, ответы быстрее и расходуют меньше лимита.
    """
    if not settings.google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to .env (see .env.example)."
        )
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        api_key=settings.google_api_key,
        thinking_level="low",
        max_retries=2,
    )
