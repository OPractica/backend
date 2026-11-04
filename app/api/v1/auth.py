from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.core.security import create_access_token, verify_password
from app.crud.refresh_token import (
    create_refresh_token,
    find_refresh_token,
    revoke_refresh_token,
)
from app.crud.user import create_user, get_user_by_email, get_user_by_id
from app.schemas.schemas import (
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

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


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return user


@router.post("/refresh", response_model=TokenResponse)
async def refresh(session: SessionDep, data: RefreshRequest) -> TokenResponse:
    token = await find_refresh_token(session, data.refresh_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )
    await revoke_refresh_token(session, token)

    user = await get_user_by_id(session, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(session, user.id)
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
