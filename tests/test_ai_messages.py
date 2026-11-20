from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.ai.language import LANGUAGES
from app.ai.messages import REFUSALS, booking_cancelled, booking_confirmation, refusal

TZ = ZoneInfo("Europe/Chisinau")
START = datetime(2030, 1, 16, 10, 0, tzinfo=TZ)
END = datetime(2030, 1, 16, 12, 0, tzinfo=TZ)


@pytest.mark.parametrize("language", LANGUAGES)
def test_booking_confirmation_contains_every_fact(language: str):
    text = booking_confirmation(language, "7-A03", START, END, 5)

    for fact in ("7-A03", "2030-01-16", "10:00", "12:00", "5"):
        assert fact in text


def test_confirmations_differ_between_languages():
    texts = {booking_confirmation(lang, "7-A03", START, END, 5) for lang in LANGUAGES}

    assert len(texts) == 3


@pytest.mark.parametrize("language", LANGUAGES)
def test_cancellation_contains_the_booking_number(language: str):
    assert "12" in booking_cancelled(language, 12)


def test_refusals_match_the_markers_used_by_the_evaluation():
    assert "только с бронированием" in refusal("ru")
    assert "doar cu rezervarea" in refusal("ro")
    assert "only help with booking" in refusal("en")
    assert set(REFUSALS) == set(LANGUAGES)
