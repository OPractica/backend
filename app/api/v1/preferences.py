from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.preferences.parser import extract_preferences
from app.services.rag.search import search_seats

router = APIRouter(prefix="/ai", tags=["AI Preferences"])


class PreferenceRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = "ru"


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
def search_seats_endpoint(request: PreferenceRequest):
    validate_language(request.language)

    result = search_seats(
        text=request.text,
        language=request.language,
    )

    return {
        **result,
        "data_source": "demo",
        "availability_checked": False,
        "booking_created": False,
    }
