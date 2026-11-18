from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import MeetingRoom, MeetingRoomBooking, User

pytestmark = pytest.mark.anyio

STATUS_URL = "/api/v1/meeting/getMeetingRoomsWithStatusByOfficeId"
BUSY_URL = "/api/v1/meeting/getBusyMeetingRoomsByOfficeId"
BOOKINGS_URL = "/api/v1/meeting/bookings"

# 2030-01-15 is a Tuesday, 09:00Z is 11:00 office time
PARAMS = {
    "officeId": 1,
    "fromDate": "2030-01-15T09:00:00Z",
    "toDate": "2030-01-15T09:30:00Z",
}
STARTS_AT = datetime(2030, 1, 15, 9, tzinfo=UTC)
ENDS_AT = datetime(2030, 1, 15, 9, 30, tzinfo=UTC)


async def add_room(
    session: AsyncSession,
    room_id: int,
    alias: str,
    office_id: int = 1,
    is_active: bool = True,
) -> MeetingRoom:
    room = MeetingRoom(
        id=room_id,
        office_id=office_id,
        email=f"{alias.lower()}@orange.md",
        alias=f"Orange {{kITchen}} - {alias}",
        capacity=10,
        equipments="Room, TV, Whiteboard",
        is_active=is_active,
    )
    session.add(room)
    await session.flush()
    return room


async def add_room_booking(
    session: AsyncSession,
    room: MeetingRoom,
    starts_at: datetime = STARTS_AT,
    ends_at: datetime = ENDS_AT,
    status: str = "confirmed",
) -> MeetingRoomBooking:
    user = User(email=f"{uuid4().hex}@example.com", password_hash="x", full_name="U")
    session.add(user)
    await session.flush()
    booking = MeetingRoomBooking(
        room_id=room.id,
        user_id=user.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
    )
    session.add(booking)
    await session.flush()
    return booking


async def auth_headers(client: AsyncClient) -> dict[str, str]:
    email = f"{uuid4().hex}@example.com"
    password = "secret-password"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Tester"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_rooms_with_status_returns_guide_fields(
    client: AsyncClient, session: AsyncSession
):
    chili = await add_room(session, 10301, "Chili")
    await add_room(session, 10302, "Pepper")
    await add_room_booking(session, chili)

    response = await client.get(STATUS_URL, params=PARAMS)

    assert response.status_code == 200
    assert response.json() == [
        {
            "roomId": 10301,
            "roomEmail": "chili@orange.md",
            "roomAlias": "Orange {kITchen} - Chili",
            "roomCapacity": "10",
            "roomEquipments": "Room, TV, Whiteboard",
            "isBusy": True,
        },
        {
            "roomId": 10302,
            "roomEmail": "pepper@orange.md",
            "roomAlias": "Orange {kITchen} - Pepper",
            "roomCapacity": "10",
            "roomEquipments": "Room, TV, Whiteboard",
            "isBusy": False,
        },
    ]


async def test_rooms_with_status_skips_other_offices_and_inactive_rooms(
    client: AsyncClient, session: AsyncSession
):
    await add_room(session, 10301, "Chili")
    await add_room(session, 20301, "Other", office_id=2)
    await add_room(session, 10303, "Closed", is_active=False)

    response = await client.get(STATUS_URL, params=PARAMS)

    assert [room["roomId"] for room in response.json()] == [10301]


async def test_unknown_office_returns_empty_list(client: AsyncClient):
    response = await client.get(STATUS_URL, params={**PARAMS, "officeId": 999})

    assert response.status_code == 200
    assert response.json() == []


async def test_busy_rooms_returns_only_busy_ids(
    client: AsyncClient, session: AsyncSession
):
    chili = await add_room(session, 10301, "Chili")
    await add_room(session, 10302, "Pepper")
    garlic = await add_room(session, 10304, "Garlic")
    await add_room_booking(session, chili)
    await add_room_booking(session, garlic)

    response = await client.get(BUSY_URL, params=PARAMS)

    assert response.status_code == 200
    assert response.json() == [10301, 10304]


@pytest.mark.parametrize(
    ("starts_at", "ends_at", "status"),
    [
        # Ends exactly when the requested range starts
        (datetime(2030, 1, 15, 8, 30, tzinfo=UTC), STARTS_AT, "confirmed"),
        (STARTS_AT, ENDS_AT, "cancelled"),
    ],
)
async def test_adjacent_or_cancelled_booking_does_not_make_room_busy(
    client: AsyncClient,
    session: AsyncSession,
    starts_at: datetime,
    ends_at: datetime,
    status: str,
):
    chili = await add_room(session, 10301, "Chili")
    await add_room_booking(session, chili, starts_at, ends_at, status)

    response = await client.get(BUSY_URL, params=PARAMS)

    assert response.json() == []


@pytest.mark.parametrize("url", [STATUS_URL, BUSY_URL])
async def test_invalid_time_range_returns_422(client: AsyncClient, url: str):
    response = await client.get(
        url,
        params={**PARAMS, "fromDate": PARAMS["toDate"], "toDate": PARAMS["fromDate"]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_time_range"


async def test_missing_office_id_returns_422(client: AsyncClient):
    params = {key: value for key, value in PARAMS.items() if key != "officeId"}

    response = await client.get(STATUS_URL, params=params)

    assert response.status_code == 422


async def test_book_room_then_it_is_busy_and_cancel_frees_it(
    client: AsyncClient, session: AsyncSession
):
    await add_room(session, 10301, "Chili")
    headers = await auth_headers(client)

    created = await client.post(
        BOOKINGS_URL,
        headers=headers,
        json={
            "room_id": 10301,
            "starts_at": PARAMS["fromDate"],
            "ends_at": PARAMS["toDate"],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "confirmed"
    assert (await client.get(BUSY_URL, params=PARAMS)).json() == [10301]

    mine = await client.get(f"{BOOKINGS_URL}/me", headers=headers)
    assert [b["id"] for b in mine.json()] == [created.json()["id"]]

    cancelled = await client.patch(
        f"{BOOKINGS_URL}/{created.json()['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (await client.get(BUSY_URL, params=PARAMS)).json() == []
    # Cancelled bookings are not listed, as with seat bookings
    assert (await client.get(f"{BOOKINGS_URL}/me", headers=headers)).json() == []


async def test_book_busy_room_returns_409(client: AsyncClient, session: AsyncSession):
    chili = await add_room(session, 10301, "Chili")
    await add_room_booking(session, chili)
    headers = await auth_headers(client)

    response = await client.post(
        BOOKINGS_URL,
        headers=headers,
        json={
            "room_id": chili.id,
            "starts_at": "2030-01-15T09:15:00Z",
            "ends_at": "2030-01-15T10:00:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "room_already_booked"


async def test_book_unknown_room_returns_409(client: AsyncClient):
    headers = await auth_headers(client)

    response = await client.post(
        BOOKINGS_URL,
        headers=headers,
        json={
            "room_id": 999,
            "starts_at": PARAMS["fromDate"],
            "ends_at": PARAMS["toDate"],
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "room_not_found"


async def test_book_room_on_weekend_returns_422(
    client: AsyncClient, session: AsyncSession
):
    await add_room(session, 10301, "Chili")
    headers = await auth_headers(client)

    response = await client.post(
        BOOKINGS_URL,
        headers=headers,
        json={
            "room_id": 10301,
            "starts_at": "2030-01-19T09:00:00Z",
            "ends_at": "2030-01-19T09:30:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "office_closed_weekend"


async def test_book_room_requires_auth(client: AsyncClient):
    response = await client.post(BOOKINGS_URL, json={})

    assert response.status_code == 401


async def test_cancel_someone_elses_room_booking_returns_404(
    client: AsyncClient, session: AsyncSession
):
    chili = await add_room(session, 10301, "Chili")
    booking = await add_room_booking(session, chili)
    headers = await auth_headers(client)

    response = await client.patch(
        f"{BOOKINGS_URL}/{booking.id}/cancel", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "booking_not_found"
