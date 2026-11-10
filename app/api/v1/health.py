from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.openapi import error_response, example_response
from app.core.db import SessionDep

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/live",
    summary="Liveness probe",
    description="Returns `ok` while the process is running. Does not touch the database.",
    responses={200: example_response("The service is running", {"status": "ok"})},
)
async def liveness():
    return {"status": "ok"}


@router.get(
    "",
    summary="Readiness probe",
    description="Returns `ok` if the service can reach the database.",
    responses={
        200: example_response(
            "The service and the database are available", {"status": "ok"}
        ),
        503: error_response("The database is unavailable", "database unavailable"),
    },
)
async def health(session: SessionDep):
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return {"status": "ok"}
