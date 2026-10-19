from fastapi import FastAPI

from app.api.v1 import health
from app.api.v1.seats import router as seats_router

app = FastAPI()
app.include_router(health.router, prefix="/api/v1")
app.include_router(seats_router, prefix="/api/v1")
