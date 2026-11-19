from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints


class VoiceProcessingResult(BaseModel):
    """Validated transcription and extracted preferences."""

    transcription: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]
    language: Literal["ru", "ro", "en"]
    attributes: dict[str, Any]
    needs_clarification: list[Any]


class VoiceTranscriptionResponse(VoiceProcessingResult):
    """Response with the stored recording metadata."""

    record_id: int = Field(gt=0)
    expires_at: datetime
