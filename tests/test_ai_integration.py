import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.services.ai_integration import process_user_text
from app.services.preferences.parser import extract_preferences


class FakeScalars:
    def all(self):
        return []


class FakeSession:
    async def scalars(self, statement):
        return FakeScalars()


def fake_get_session():
    yield FakeSession()


RU_TEXT = (
    "\u0425\u043e\u0447\u0443 \u0442\u0438\u0445\u043e\u0435 "
    "\u043c\u0435\u0441\u0442\u043e \u0432\u043e\u0437\u043b\u0435 "
    "\u043e\u043a\u043d\u0430 \u0441 \u0434\u0432\u0443\u043c\u044f "
    "\u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0430\u043c\u0438"
)


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = fake_get_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_preferences_http(client):
    response = client.post(
        "/api/v1/ai/preferences",
        json={"text": RU_TEXT, "language": "ru"},
    )
    assert response.status_code == 200
    assert response.json()["attributes"] == {
        "near_window": True,
        "quiet": True,
        "monitors_min": 2,
    }


def test_database_search_http(client):
    response = client.post(
        "/api/v1/ai/search-seats",
        json={
            "text": RU_TEXT,
            "language": "ru",
            "mode": "database",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["matches"] == []
    assert result["total"] == 0
    assert result["data_source"] == "database"
    assert result["availability_checked"] is False
    assert result["booking_created"] is False


def test_demo_search_http(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_demo_search", True)
    response = client.post(
        "/api/v1/ai/search-seats",
        json={
            "text": RU_TEXT,
            "language": "ru",
            "mode": "demo",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["data_source"] == "demo"
    assert result["availability_checked"] is False


@pytest.mark.parametrize("language", ["ru", "ro", "en"])
def test_invalid_text_http(client, language):
    response = client.post(
        "/api/v1/ai/preferences",
        json={"text": "", "language": language},
    )
    assert response.status_code == 422


def test_unsupported_language_http(client):
    response = client.post(
        "/api/v1/ai/preferences",
        json={"text": "desk", "language": "de"},
    )
    assert response.status_code == 400


def test_invalid_search_mode_http(client):
    response = client.post(
        "/api/v1/ai/search-seats",
        json={
            "text": "desk",
            "language": "en",
            "mode": "unknown",
        },
    )
    assert response.status_code == 422


def test_ai_integration_database():
    result = asyncio.run(
        process_user_text(
            RU_TEXT,
            language="ru",
            session=FakeSession(),
            mode="database",
        )
    )
    assert result["preferences"]["attributes"]["near_window"] is True
    assert result["seat_candidates"] == []
    assert result["data_source"] == "database"
    assert result["availability_checked"] is False
    assert result["booking_created"] is False
    assert "Availability has NOT been checked" not in result["context"]


def test_ai_integration_demo():
    result = asyncio.run(process_user_text(RU_TEXT, language="ru", mode="demo"))
    assert len(result["seat_candidates"]) == 1
    assert result["data_source"] == "demo"
    assert result["availability_checked"] is False
    assert result["booking_created"] is False


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ru", RU_TEXT),
        ("ro", "Vreau un loc de lucru langa fereastra"),
        ("en", "I want a quiet desk near the window"),
    ],
)
def test_language_parsing_returns_structure(language, text):
    result = extract_preferences(text, language)
    assert result["language"] == language
    assert isinstance(result["attributes"], dict)
    assert isinstance(result["needs_clarification"], list)


def test_demo_search_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_demo_search", False)

    response = client.post(
        "/api/v1/ai/search-seats",
        json={"text": "desk", "language": "en", "mode": "demo"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Demo search is disabled"


@pytest.mark.parametrize("language", ["ru", "ro", "en"])
def test_actual_preferences_for_each_language(language):
    from app.services.preferences.dictionary import PREFERENCE_DICTIONARY

    phrases = [
        PREFERENCE_DICTIONARY["near_window"][language][0],
        PREFERENCE_DICTIONARY["quiet"][language][0],
        PREFERENCE_DICTIONARY["two_monitors"][language][0],
    ]

    result = extract_preferences(" ".join(phrases), language)

    assert result["attributes"] == {
        "near_window": True,
        "quiet": True,
        "monitors_min": 2,
    }
