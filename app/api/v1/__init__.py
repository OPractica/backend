from fastapi import APIRouter

from app.api.v1 import auth, bookings, seats, users

api_router = APIRouter(prefix="/api/v1")
for r in (auth.router, users.router, seats.router, bookings.router):
    api_router.include_router(r)
