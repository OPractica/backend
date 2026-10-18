import os
import tempfile
from datetime import date, timedelta

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import mail

SENT = []


async def fake_send(to, subject, body, strict=False):
    SENT.append((to, subject, body))


@pytest.fixture(scope="module")
def c():
    mail.send_mail = fake_send
    with TestClient(app) as client:
        yield client


def signup(c, email, name="Ion Test"):
    r = c.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "phone": "+373 600 00000", "password": "secret1"},
    )
    assert r.status_code == 202, r.text
    code = SENT[-1][2].split("code is: ")[1][:6]
    r = c.post("/api/v1/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_only_outlook(c):
    r = c.post(
        "/api/v1/auth/register",
        json={"full_name": "A B", "email": "a@gmail.com", "phone": "+373 600 00000", "password": "secret1"},
    )
    assert r.status_code == 422


def test_code_required_and_flow(c):
    r = c.post(
        "/api/v1/auth/register",
        json={"full_name": "Ion Test", "email": "ion@outlook.com", "phone": "+373 600 00000", "password": "secret1"},
    )
    assert r.status_code == 202
    assert SENT[-1][0] == "ion@outlook.com"
    # not an account yet
    assert c.post("/api/v1/auth/login", json={"email": "ion@outlook.com", "password": "secret1"}).status_code == 401
    assert (
        c.post("/api/v1/auth/verify", json={"email": "ion@outlook.com", "code": "000000"}).json()["detail"]
        == "Wrong code."
    )
    code = SENT[-1][2].split("code is: ")[1][:6]
    t = c.post("/api/v1/auth/verify", json={"email": "ion@outlook.com", "code": code}).json()
    assert c.post("/api/v1/auth/login", json={"email": "ion@outlook.com", "password": "secret1"}).status_code == 200
    assert c.post("/api/v1/auth/login", json={"email": "ion@outlook.com", "password": "bad123"}).status_code == 401
    r2 = c.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r2.status_code == 200
    assert c.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401  # rotated


def test_booking_flow(c):
    a = signup(c, "ana@outlook.com", "Ana")
    b = signup(c, "bob@hotmail.com", "Bob")
    day = (date.today() + timedelta(days=1)).isoformat()
    r = c.post("/api/v1/bookings", json={"seat_id": "s5", "date": day}, headers=a)
    assert r.status_code == 201, r.text
    assert r.json()["start"] == "09:00" and r.json()["end"] == "18:00"
    to, subj, body = SENT[-1]
    assert to == "ana@outlook.com" and day[:4] in body and "09:00-18:00" in body and "Booking confirmed" in subj
    # others see it busy, owner sees mine, nobody can double book
    av = {x["seat_id"]: x for x in c.get(f"/api/v1/seats/availability?date={day}", headers=b).json()}
    assert av["s5"]["status"] == "busy" and av["s5"]["booked_by"] == "Ana" and av["s6"]["status"] == "free"
    assert c.get(f"/api/v1/seats/availability?date={day}", headers=a).json()[4]["status"] == "mine"
    assert c.post("/api/v1/bookings", json={"seat_id": "s5", "date": day}, headers=b).status_code == 409
    assert (
        c.post("/api/v1/bookings", json={"seat_id": "s6", "date": day}, headers=a).status_code == 409
    )  # same user, same time
    assert c.post("/api/v1/bookings", json={"seat_id": "s6", "date": "2020-01-01"}, headers=b).status_code == 422
    assert c.post("/api/v1/bookings", json={"seat_id": "s6", "date": day}).status_code == 401
    mine = c.get("/api/v1/bookings/me", headers=a).json()
    assert len(mine) == 1
    assert c.patch(f"/api/v1/bookings/{mine[0]['id']}/cancel", headers=b).status_code == 404
    assert c.patch(f"/api/v1/bookings/{mine[0]['id']}/cancel", headers=a).status_code == 200
    assert "cancelled" in SENT[-1][1].lower()
    assert c.post("/api/v1/bookings", json={"seat_id": "s5", "date": day}, headers=b).status_code == 201


def test_profile_and_settings(c):
    h = signup(c, "eva@outlook.com", "Eva")
    r = c.patch(
        "/api/v1/users/me", json={"full_name": "Eva Pop", "settings": {"theme": "dark", "notify": False}}, headers=h
    )
    assert r.json()["full_name"] == "Eva Pop" and r.json()["settings"] == {"theme": "dark", "notify": False}
    n = len(SENT)
    day = (date.today() + timedelta(days=2)).isoformat()
    assert c.post("/api/v1/bookings", json={"seat_id": "s9", "date": day}, headers=h).status_code == 201
    assert len(SENT) == n  # notifications switched off
    assert len(c.get("/api/v1/seats").json()) > 100
