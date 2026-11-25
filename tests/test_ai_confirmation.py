import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.ai.confirmation import confirmations_for, messages_of_this_turn

BOOKED = "booking created: booking id 15, seat 7-A03, from 2030-01-15 09:00 to 2030-01-15 10:30"


def tool_message(name: str, content: str) -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id="call_1")


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (
            "ru",
            "Место 7-A03 забронировано на 2030-01-15 с 09:00 до 10:30. Номер брони: 15.",
        ),
        (
            "ro",
            "Locul 7-A03 a fost rezervat pentru 2030-01-15, între 09:00 și 10:30. Numărul rezervării: 15.",
        ),
        (
            "en",
            "Seat 7-A03 is booked for 2030-01-15 from 09:00 to 10:30. Booking number: 15.",
        ),
    ],
)
def test_booking_result_becomes_a_template_in_the_dialog_language(language, expected):
    messages = [
        HumanMessage("book"),
        tool_message("book_seat", BOOKED),
        AIMessage("ok"),
    ]
    assert confirmations_for(messages, language) == [expected]


def test_cancel_result_becomes_a_template():
    messages = [
        HumanMessage("cancel"),
        tool_message("cancel_my_booking", "booking 15 cancelled"),
        AIMessage("ok"),
    ]
    assert confirmations_for(messages, "en") == ["Booking 15 is cancelled."]


@pytest.mark.parametrize(
    "content",
    [
        "no free seats for this time",
        "error seat_taken: the seat is already booked",
        "seat=7-A03 zone=window properties={}",
    ],
)
def test_other_tool_results_give_no_confirmation(content):
    messages = [HumanMessage("x"), tool_message("book_seat", content), AIMessage("ok")]
    assert confirmations_for(messages, "ru") == []


def test_search_result_is_never_confirmed_as_a_booking():
    messages = [
        HumanMessage("x"),
        tool_message("search_free_seats", BOOKED),
        AIMessage("ok"),
    ]
    assert confirmations_for(messages, "ru") == []


def test_only_the_current_turn_is_confirmed():
    messages = [
        HumanMessage("first"),
        tool_message("book_seat", BOOKED),
        AIMessage("done"),
        HumanMessage("second"),
        AIMessage("anything else?"),
    ]
    assert messages_of_this_turn(messages) == messages[4:]
    assert confirmations_for(messages, "ru") == []


def test_two_actions_in_one_turn_give_two_confirmations():
    messages = [
        HumanMessage("x"),
        tool_message("cancel_my_booking", "booking 3 cancelled"),
        tool_message("book_seat", BOOKED),
        AIMessage("ok"),
    ]
    assert len(confirmations_for(messages, "en")) == 2
