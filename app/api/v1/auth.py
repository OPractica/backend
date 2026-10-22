from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionDep
from app.crud.user import create_user, get_user_by_email
from app.schemas.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(session: SessionDep, data: UserCreate):
    existing = await get_user_by_email(session, data.email)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email is already in use"
        )

    try:
        user = await create_user(session, data)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email is already in use"
        )
    return user
