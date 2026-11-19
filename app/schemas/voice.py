from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints
from typing_extensions import TypedDict


class VoiceAttributes(TypedDict, total=False):
    """Optional seat constraints returned by the preference parser.

    Missing means not specified. False means explicitly unwanted.
    """

    __pydantic_config__ = ConfigDict(extra="forbid")

    near_window: StrictBool
    quiet: StrictBool
    docking_station: StrictBool
    monitors_min: Annotated[int, Field(gt=0, strict=True)]


class VoiceProcessingResult(BaseModel):
    """Validated transcription and extracted preferences."""

    transcription: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]
    language: Literal["ru", "ro", "en"]
    attributes: VoiceAttributes
    needs_clarification: list[Literal["cozy"]]


class VoiceTranscriptionResponse(VoiceProcessingResult):
    """Response with the stored recording metadata."""

    record_id: int = Field(gt=0)
    expires_at: datetime
