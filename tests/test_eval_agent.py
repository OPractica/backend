from datetime import date

from scripts.eval_agent import lang_of, next_weekday, problems_for
from scripts.eval_cases import CASES, Step

TODAY = date(2030, 1, 15)  # вторник


def test_lang_of_detects_russian_romanian_and_english():
    assert lang_of("Бронь создана: место 7-A01") == "ru"
    assert lang_of("Locul 7-A03 a fost rezervat pentru mâine") == "ro"
    assert lang_of("Seat 7-A01 is booked for tomorrow") == "en"


def test_next_weekday_is_strictly_after_today():
    assert next_weekday(TODAY, 4) == date(2030, 1, 18)  # ближайшая пятница
    assert next_weekday(TODAY, 1) == date(
        2030, 1, 22
    )  # вторник через неделю, не сегодня


def test_problems_for_reports_missing_and_forbidden_tools():
    step = Step("x", tools=("search_free_seats",), forbid=("book_seat",))

    assert (
        problems_for(step, [{"name": "search_free_seats", "args": {}}], "", TODAY) == []
    )
    problems = problems_for(step, [{"name": "book_seat", "args": {}}], "", TODAY)
    assert "не вызван search_free_seats" in problems
    assert "нельзя было вызывать book_seat" in problems


def test_problems_for_checks_refusal_and_language():
    step = Step("x", no_tools=True, refusal=True, lang="en")

    ok = "I can only help with booking workspaces. Would you like to book a seat?"
    assert problems_for(step, [], ok, TODAY) == []
    assert problems_for(step, [], "Вот шутка про стул: ...", TODAY)


def test_problems_for_checks_the_search_date():
    step = Step("x", tools=("search_free_seats",), search_day=2)
    on_time = [{"name": "search_free_seats", "args": {"start": "2030-01-17T09:00"}}]
    too_early = [{"name": "search_free_seats", "args": {"start": "2030-01-16T09:00"}}]

    assert problems_for(step, on_time, "", TODAY) == []
    assert problems_for(step, too_early, "", TODAY)


def test_every_case_has_a_unique_name_and_checks_something():
    names = [case.name for case in CASES]

    assert len(names) == len(set(names))
    for case in CASES:
        assert case.steps
        has_check = case.bookings is not None or any(
            step.tools or step.forbid or step.no_tools or step.refusal or step.lang
            for step in case.steps
        )
        assert has_check, case.name
