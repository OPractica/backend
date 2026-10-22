"""Проверка подключения к модели.

Запуск: uv run python -m scripts.check_llm
"""

from app.ai.llm import get_llm

answer = get_llm().invoke("Привет! Представься одним предложением.")
print(answer.content)
