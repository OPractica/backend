from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

DEFAULT_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "unprocessable_entity",
    429: "too_many_requests",
    503: "service_unavailable",
}


class APIError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = getattr(exc, "code", None) or DEFAULT_CODES.get(exc.status_code, "error")
    return JSONResponse(
        {"detail": exc.detail, "code": code},
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        {"detail": jsonable_encoder(exc.errors()), "code": "validation_error"},
        status_code=422,
    )
