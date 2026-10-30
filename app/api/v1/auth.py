from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionDep
from app.core.security import create_access_token, verify_password
from app.crud.refresh_token import create_refresh_token
from app.crud.user import create_user, get_user_by_email
from app.schemas.schemas import TokenResponse, UserCreate, UserLogin, UserResponse

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


@router.post("/login", response_model=TokenResponse)
async def login(session: SessionDep, data: UserLogin) -> TokenResponse:
    user = await get_user_by_email(session, data.email)

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user is not active"
        )
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(session, user.id)
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
