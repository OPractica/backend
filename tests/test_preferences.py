import pytest

from app.services.preferences.parser import extract_preferences


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        (
            "ru",
            "Хочу тихое место возле окна с двумя мониторами",
            {"near_window": True, "quiet": True, "monitors_min": 2},
        ),
        (
            "ro",
            "Vreau un loc liniștit lângă fereastră cu două monitoare",
            {"near_window": True, "quiet": True, "monitors_min": 2},
        ),
        (
            "en",
            "I want a quiet place near the window with two monitors",
            {"near_window": True, "quiet": True, "monitors_min": 2},
        ),
        (
            "ro",
            "Vreau un birou langa geam cu doua ecrane",
            {"near_window": True, "monitors_min": 2},
        ),
        (
            "en",
            "I need a laptop docking station",
            {"docking_station": True},
        ),
        (
            "ru",
            "Мне нужен стол у самого окна",
            {"near_window": True},
        ),
    ],
)
def test_multilingual_preference_extraction(language, text, expected):
    result = extract_preferences(text, language)

    assert result["language"] == language
    assert result["attributes"] == expected
    assert result["needs_clarification"] == []


@pytest.mark.parametrize("language", ["ru", "ro", "en"])
def test_empty_preferences(language):
    result = extract_preferences("12345", language)

    assert result["attributes"] == {}
    assert result["needs_clarification"] == []


def test_ambiguous_preference_requires_clarification():
    result = extract_preferences("Хочу уютное место", "ru")

    assert result["attributes"] == {}
    assert result["needs_clarification"] == ["cozy"]


def test_unsupported_language():
    with pytest.raises(ValueError, match="Unsupported language"):
        extract_preferences("Un loc liniștit", "fr")
