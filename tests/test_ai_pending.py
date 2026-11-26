import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.ai.pending import PENDING_KEY, pending_from_history, read_reply

QUESTION = AIMessage(
    "Cancel?", additional_kwargs={PENDING_KEY: [{"kind": "seat", "id": 5}]}
)


@pytest.mark.parametrize(
    "text",
    [
        "да",
        "Да.",
        "Да, отмени.",
        "да, отмени бронь пожалуйста",
        "ок",
        "yes",
        "Yes, cancel it!",
        "yes please",
        "da",
        "Da, te rog.",
        "da, anulează",
    ],
)
def test_clear_agreement_is_yes(text):
    assert read_reply(text) == "yes"


@pytest.mark.parametrize(
    "text",
    [
        "нет",
        "Нет, спасибо",
        "не отменяй, нет",
        "не надо",
        "да нет",
        "no",
        "No, keep it",
        "don't cancel",
        "nu",
        "nu anula",
        "Nu, mulțumesc.",
    ],
)
def test_refusal_is_no(text):
    assert read_reply(text) == "no"


@pytest.mark.parametrize(
    "text",
    [
        "да, но сначала покажи мои брони",
        "нет, отмени другую на завтра",
        "отмени бронь 7",
        "а какое это место?",
        "yes and book 7-A03",
        "nu știu",
        "7",
        "",
    ],
)
def test_anything_else_is_not_an_answer(text):
    assert read_reply(text) is None


def test_pending_is_read_from_the_question_right_before_the_reply():
    history = [HumanMessage("cancel"), QUESTION, HumanMessage("yes")]

    assert pending_from_history(history) == [{"kind": "seat", "id": 5}]


def test_an_old_question_does_not_count():
    history = [
        QUESTION,
        HumanMessage("show my bookings"),
        AIMessage("Here they are"),
        HumanMessage("yes"),
    ]

    assert pending_from_history(history) == []


def test_no_pending_in_an_empty_dialog():
    assert pending_from_history([HumanMessage("yes")]) == []
