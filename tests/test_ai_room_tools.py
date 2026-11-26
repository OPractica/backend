from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import tools as ai_tools
from app.ai.tools import MEETING_ROOMS_OFFICE_ID, make_tools
from app.models.database import MeetingRoom, MeetingRoomBooking, User

pytestmark = pytest.mark.anyio

START = "2030-01-15T09:00"
END = "2030-01-15T10:00"


async def add_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash="x", full_name="Test User")
    session.add(user)
    await session.flush()
    return user


async def add_room(
    session: AsyncSession,
    room_id: int,
    alias: str,
    capacity: int = 8,
    equipments: str = "TV, Whiteboard",
) -> MeetingRoom:
    room = MeetingRoom(
        id=room_id,
        office_id=MEETING_ROOMS_OFFICE_ID,
        email=f"room{room_id}@example.com",
        alias=alias,
        capacity=capacity,
        equipments=equipments,
    )
    session.add(room)
    await session.flush()
    return room


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await add_user(session, "rooms-me@example.com")


@pytest.fixture
async def tools(monkeypatch, session: AsyncSession, user: User) -> dict:
    @asynccontextmanager
    async def test_session_local():
        yield session

    monkeypatch.setattr(ai_tools, "SessionLocal", test_session_local)
    return {tool.name: tool for tool in make_tools(user.id)}


async def test_search_lists_free_rooms_with_capacity(session, tools):
    await add_room(session, 91001, "Chili", capacity=8)
    await add_room(session, 91002, "Cabină 1", capacity=1, equipments="")

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END}
    )

    assert "room=Chili capacity=8 equipment=TV, Whiteboard" in result
    assert "room=Cabină 1 capacity=1 equipment=none" in result


async def test_search_filters_by_capacity(session, tools):
    await add_room(session, 91001, "Chili", capacity=8)
    await add_room(session, 91002, "Cabină 1", capacity=1)

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END, "min_capacity": 6}
    )

    assert "Chili" in result
    assert "Cabină 1" not in result


async def test_search_filters_by_equipment(session, tools):
    await add_room(session, 91001, "Chili", equipments="TV, Whiteboard")
    await add_room(session, 91002, "Ketchup", equipments="TV")

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END, "equipment": "Whiteboard"}
    )

    assert "room=Chili" in result
    assert "Ketchup" not in result


async def test_equipment_needs_every_item_and_ignores_case_and_spaces(session, tools):
    await add_room(session, 91001, "Chili", equipments="TV,Whiteboard")
    await add_room(session, 91002, "Ketchup", equipments="TV")

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END, "equipment": " whiteboard ,  tv "}
    )

    assert "room=Chili" in result
    assert "Ketchup" not in result


async def test_search_combines_capacity_and_equipment(session, tools):
    await add_room(session, 91001, "Chili", capacity=8, equipments="TV, Whiteboard")
    await add_room(session, 91002, "Ketchup", capacity=6, equipments="TV")
    await add_room(session, 91003, "Boiling Room", capacity=10, equipments="TV")

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END, "min_capacity": 7, "equipment": "TV"}
    )

    assert "room=Chili capacity=8" in result
    assert "room=Boiling Room capacity=10" in result
    assert "Ketchup" not in result


async def test_search_says_when_no_free_room_fits(session, tools):
    await add_room(session, 91001, "Ketchup", capacity=6, equipments="TV")

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END, "min_capacity": 6, "equipment": "Whiteboard"}
    )

    assert result == "no free meeting room has enough seats and all the equipment"


async def test_search_skips_busy_rooms(session, tools, user):
    room = await add_room(session, 91001, "Chili")
    session.add(
        MeetingRoomBooking(
            user_id=user.id,
            room_id=room.id,
            starts_at=datetime(2030, 1, 15, 7, tzinfo=UTC),
            ends_at=datetime(2030, 1, 15, 8, tzinfo=UTC),
        )
    )
    await session.flush()

    result = await tools["search_free_meeting_rooms"].ainvoke(
        {"start": START, "end": END}
    )

    assert result == "no free meeting rooms for this time"


async def test_book_room_by_name_creates_a_booking_for_the_user(session, tools, user):
    room = await add_room(session, 91001, "Ketchup")

    result = await tools["book_meeting_room"].ainvoke(
        {"room": "ketchup", "start": START, "end": END}
    )

    assert result.startswith("meeting room booking created: booking id ")
    assert "room Ketchup, from 2030-01-15 09:00 to 2030-01-15 10:00" in result
    booking = await session.scalar(
        select(MeetingRoomBooking).where(MeetingRoomBooking.room_id == room.id)
    )
    assert booking is not None and booking.user_id == user.id


async def test_room_name_ignores_case_and_diacritics(session, tools):
    await add_room(session, 91001, "Cabină 1")

    result = await tools["book_meeting_room"].ainvoke(
        {"room": "cabina 1", "start": START, "end": END}
    )

    assert "room Cabină 1" in result


@pytest.mark.parametrize("name", ["Boiling Room", "boiling room", " BOILING   ROOM "])
async def test_book_boiling_room_by_its_new_name(session, tools, name):
    await add_room(session, 91003, "Boiling Room", capacity=10)

    result = await tools["book_meeting_room"].ainvoke(
        {"room": name, "start": START, "end": END}
    )

    assert result.startswith("meeting room booking created: booking id ")
    assert "room Boiling Room, from 2030-01-15 09:00" in result


async def test_book_unknown_room_returns_an_error_code(session, tools):
    # The old name doesn't book the renamed room
    await add_room(session, 91001, "Chili")

    result = await tools["book_meeting_room"].ainvoke(
        {"room": "Sala 1", "start": START, "end": END}
    )

    assert result.startswith("error room_not_found:")


async def test_second_booking_of_the_same_room_is_rejected(session, tools):
    await add_room(session, 91001, "Ketchup")
    args = {"room": "Ketchup", "start": START, "end": END}
    await tools["book_meeting_room"].ainvoke(args)

    second = await tools["book_meeting_room"].ainvoke(args)

    assert second.startswith("error room_already_booked:")


async def test_booking_outside_office_hours_is_rejected(session, tools):
    await add_room(session, 91001, "Ketchup")

    result = await tools["book_meeting_room"].ainvoke(
        {"room": "Ketchup", "start": "2030-01-15T22:00", "end": "2030-01-15T23:00"}
    )

    assert result.startswith("error outside_office_hours:")


async def test_list_and_cancel_own_room_booking(session, tools):
    await add_room(session, 91001, "Ketchup")
    created = await tools["book_meeting_room"].ainvoke(
        {"room": "Ketchup", "start": START, "end": END}
    )
    booking_id = int(created.split("booking id ")[1].split(",")[0])

    listed = await tools["list_my_meeting_room_bookings"].ainvoke({})
    cancelled = await tools["cancel_meeting_room_booking"].ainvoke(
        {"booking_id": booking_id}
    )

    assert f"meeting room booking {booking_id}: room Ketchup" in listed
    assert cancelled == f"meeting room booking {booking_id} cancelled"


async def test_cannot_cancel_someone_elses_room_booking(session, tools):
    room = await add_room(session, 91001, "Ketchup")
    owner = await add_user(session, "rooms-owner@example.com")
    foreign = MeetingRoomBooking(
        user_id=owner.id,
        room_id=room.id,
        starts_at=datetime(2030, 1, 15, 7, tzinfo=UTC),
        ends_at=datetime(2030, 1, 15, 8, tzinfo=UTC),
    )
    session.add(foreign)
    await session.flush()

    result = await tools["cancel_meeting_room_booking"].ainvoke(
        {"booking_id": foreign.id}
    )

    assert result.startswith("error booking_not_found:")
    assert foreign.status == "confirmed"


async def test_no_bookings_message(tools):
    assert await tools["list_my_meeting_room_bookings"].ainvoke({}) == (
        "the user has no active meeting room bookings"
    )
