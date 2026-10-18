from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.db import init_db
from app.seed import seed_seats


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_seats()
    yield


app = FastAPI(title="Workplace Booking API", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# The website itself (static/index.html) is served by the same app, so no CORS setup is needed.
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static", html=True), name="site")
