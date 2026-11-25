import pytest

from app.ai.language import detect_confident, detect_language, dialog_language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Забронируй место у окна завтра", "ru"),
        ("Давай первое", "ru"),
        ("Book me a seat with two monitors tomorrow", "en"),
        ("The second one, please", "en"),
        ("Vreau un loc liniștit poimâine de la 10 la 12", "ro"),
        ("Rezervă-mi orice loc mâine între 13 și 14", "ro"),
        ("Primul, vă rog", "ro"),
        ("poimaine intre 10 si 12", "ro"),
    ],
)
def test_detect_language(text: str, expected: str):
    assert detect_language(text) == expected


def test_text_without_letters_keeps_the_default():
    assert detect_language("7-A03") == "ru"
    assert detect_language("7-A03", default="en") == "en"
    assert detect_language("") == "ru"


def test_hint_from_speech_recognition_wins():
    assert detect_language("ok", hint="ro") == "ro"
    assert detect_language("Привет", hint="en") == "en"


def test_seat_names_and_numbers_do_not_change_the_language():
    assert detect_language("Забронируй 7-A03") == "ru"
    assert detect_language("Book 7-A03") == "en"
    assert detect_language("7-A03", default="ro") == "ro"


@pytest.mark.parametrize("text", ["ok", "da", "yes", "7-A03", "1", ""])
def test_short_or_letterless_text_is_not_confident(text):
    assert detect_confident(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Да", "ru"), ("Primul, vă rog", "ro"), ("Book me a seat please", "en")],
)
def test_clear_text_is_confident(text, expected):
    assert detect_confident(text) == expected


def test_dialog_language_skips_short_replies():
    assert dialog_language(["ok", "Bună ziua, vreau un loc"]) == "ro"
    assert dialog_language(["7-A03", "Book a seat for tomorrow"]) == "en"


def test_dialog_language_hint_and_default():
    assert dialog_language(["Привет"], hint="en") == "en"
    assert dialog_language(["ok", "1"]) == "ru"
    assert dialog_language([], default="en") == "en"
