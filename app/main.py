from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.health import router as health_router
from app.api.v1.seats import router as seats_router
from app.core.config import settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(seats_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
