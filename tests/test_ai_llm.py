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
