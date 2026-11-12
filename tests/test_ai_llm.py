import pytest

from app.ai.llm import get_llm
from app.core.config import settings


def test_get_llm_uses_model_and_key_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "gemini-test-model")

    llm = get_llm()

    assert llm.model == "gemini-test-model"
    assert llm.google_api_key.get_secret_value() == "test-key"


def test_get_llm_leaves_temperature_at_the_default(monkeypatch):
    # Google recommends the default temperature for Gemini 3 models
    monkeypatch.setattr(settings, "google_api_key", "test-key")

    assert get_llm().temperature is None


def test_get_llm_fails_clearly_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "")

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        get_llm()


def test_get_llm_builds_a_local_ollama_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "local-test-model")
    monkeypatch.setattr(settings, "ollama_base_url", "http://192.168.0.10:11434")
    monkeypatch.setattr(settings, "google_api_key", "")

    llm = get_llm()

    assert type(llm).__name__ == "ChatOllama"
    assert llm.model == "local-test-model"
    assert llm.base_url == "http://192.168.0.10:11434"
    # The local server needs no key, the context is set explicitly, thinking is off
    assert llm.num_ctx == 8192
    assert llm.reasoning is False
