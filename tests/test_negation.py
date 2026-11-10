import pytest

from app.services.preferences.parser import extract_preferences


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ru", "Не хочу место у окна"),
        ("ro", "Nu vreau un loc lângă geam"),
        ("en", "I don't want a window seat"),
    ],
)
def test_negative_window_preference(language, text):
    result = extract_preferences(text, language)

    assert result["attributes"]["near_window"] is False


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ru", "Не хочу тихое место"),
        ("ro", "Nu vreau un loc liniștit"),
        ("en", "I don't want a quiet place"),
    ],
)
def test_negative_quiet_preference(language, text):
    result = extract_preferences(text, language)

    assert result["attributes"]["quiet"] is False


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ru", "Мне не обязательно тихое место"),
        ("ro", "Nu neapărat un loc liniștit"),
        ("en", "Not necessarily a quiet place"),
    ],
)
def test_optional_quiet_preference(language, text):
    result = extract_preferences(text, language)

    assert "quiet" not in result["attributes"]


def test_negative_and_positive_preferences_together():
    result = extract_preferences(
        "I don't want a window seat, but I want a quiet place",
        "en",
    )

    assert result["attributes"]["near_window"] is False
    assert result["attributes"]["quiet"] is True


def test_negation_does_not_cross_sentences():
    result = extract_preferences(
        "I don't want a quiet place. I want a desk near the window",
        "en",
    )

    assert result["attributes"]["quiet"] is False
    assert result["attributes"]["near_window"] is True


def test_positive_preference_still_works():
    result = extract_preferences(
        "Хочу тихое место возле окна",
        "ru",
    )

    assert result["attributes"]["quiet"] is True
    assert result["attributes"]["near_window"] is True


@pytest.mark.parametrize(
    ("language", "text"),
    [
        (
            "ru",
            "Не хочу место у окна, но хочу место с двумя мониторами",
        ),
        (
            "ro",
            "Nu vreau un loc lângă geam, vreau două monitoare",
        ),
        (
            "en",
            "I don't want a window seat, but I want two monitors",
        ),
    ],
)
def test_negative_window_with_positive_monitors(language, text):
    result = extract_preferences(text, language)

    assert result["attributes"]["near_window"] is False
    assert result["attributes"]["monitors_min"] == 2


def test_russian_negation_between_sentences():
    result = extract_preferences(
        "Не хочу тихое место. Хочу стол у самого окна",
        "ru",
    )

    assert result["attributes"]["quiet"] is False
    assert result["attributes"]["near_window"] is True


def test_positive_request_without_negation():
    result = extract_preferences(
        "I want a quiet desk near the window",
        "en",
    )

    assert result["attributes"]["near_window"] is True
    assert result["attributes"]["quiet"] is True
