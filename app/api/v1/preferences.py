from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.db import SessionDep
from app.services.preferences.parser import extract_preferences
from app.services.rag.search import search_seats

router = APIRouter(prefix="/ai", tags=["AI Preferences"])


class PreferenceRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = "ru"


class SeatSearchRequest(PreferenceRequest):
    mode: Literal["database", "demo"] = "database"


def validate_language(language: str) -> None:
    if language not in {"ru", "ro", "en"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported language. Use ru, ro or en.",
        )


@router.post("/preferences")
def parse_preferences(request: PreferenceRequest):
    validate_language(request.language)
    return extract_preferences(
        text=request.text,
        language=request.language,
    )


@router.post("/search-seats")
async def search_seats_endpoint(
    request: SeatSearchRequest,
    session: SessionDep,
):
    validate_language(request.language)

    if request.mode == "demo" and not settings.allow_demo_search:
        raise HTTPException(
            status_code=403,
            detail="Demo search is disabled",
        )

    return await search_seats(
        text=request.text,
        language=request.language,
        session=session,
        mode=request.mode,
    )
