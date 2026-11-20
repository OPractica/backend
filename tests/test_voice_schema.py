import pytest
from pydantic import ValidationError

from app.schemas.voice import VoiceProcessingResult, VoiceTranscriptionResponse


def make_result(**overrides):
    data = {
        "transcription": "I need a quiet seat away from the window",
        "language": "en",
        "attributes": {"quiet": True, "near_window": False, "monitors_min": 2},
        "needs_clarification": [],
    }
    data.update(overrides)
    return data


def test_preference_schema_preserves_negative_and_missing_fields():
    result = VoiceProcessingResult.model_validate(
        make_result(attributes={"near_window": False})
    )

    assert result.model_dump(mode="json")["attributes"] == {"near_window": False}


def test_preference_schema_accepts_ambiguous_preference():
    result = VoiceProcessingResult.model_validate(
        make_result(attributes={}, needs_clarification=["cozy"])
    )

    assert result.needs_clarification == ["cozy"]


@pytest.mark.parametrize(
    "attributes",
    [
        {"quiet": "true"},
        {"near_window": 1},
        {"monitors_min": 0},
        {"monitors_min": True},
        {"unexpected_field": True},
    ],
)
def test_preference_schema_rejects_invalid_attributes(attributes):
    with pytest.raises(ValidationError):
        VoiceProcessingResult.model_validate(make_result(attributes=attributes))


def test_preference_schema_rejects_unknown_clarification():
    with pytest.raises(ValidationError):
        VoiceProcessingResult.model_validate(
            make_result(needs_clarification=["unknown"])
        )


def test_voice_openapi_documents_supported_fields():
    schema = VoiceTranscriptionResponse.model_json_schema()
    attributes = schema["$defs"]["VoiceAttributes"]

    assert attributes["additionalProperties"] is False
    assert set(attributes["properties"]) == {
        "near_window",
        "quiet",
        "docking_station",
        "monitors_min",
    }
    assert attributes["properties"]["monitors_min"]["type"] == "integer"
