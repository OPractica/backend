from typing import Any

from app.schemas.schemas import ErrorResponse, ValidationErrorResponse

OPENAPI_JSON = "application/json"


def error_response(description: str, detail: str) -> dict[str, Any]:
    """OpenAPI entry for an error answered as {"detail": "..."}."""
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {OPENAPI_JSON: {"example": {"detail": detail}}},
    }


def rule_or_validation_error(description: str, detail: str) -> dict[str, Any]:
    """422 entry: a domain rule error or a standard FastAPI validation error."""
    return {
        "model": ErrorResponse | ValidationErrorResponse,
        "description": description,
        "content": {OPENAPI_JSON: {"example": {"detail": detail}}},
    }


def example_response(description: str, example: Any) -> dict[str, Any]:
    """OpenAPI entry for a successful response with an example body."""
    return {
        "description": description,
        "content": {OPENAPI_JSON: {"example": example}},
    }


AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: error_response("Access token is missing, expired or invalid", "token expired"),
    403: error_response("The user is deactivated", "user is not active"),
}
