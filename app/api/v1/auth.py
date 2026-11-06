from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser
from app.core.db import SessionDep
from app.core.security import create_access_token, verify_password
from app.crud.refresh_token import (
    create_refresh_token,
    find_refresh_token,
    revoke_refresh_token,
    revoke_token_family,
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
    if token is None or token.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )
    if token.revoked_at is not None:
        # A rotated token came back: it may be stolen, so end the whole login
        # session. Commit before raising, otherwise the revoke is rolled back.
        await revoke_token_family(session, token.family_id)
        await session.commit()
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
    refresh_token = await create_refresh_token(session, user.id, token.family_id)
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
async def logout(session: SessionDep, data: RefreshRequest) -> None:
    # Always 204: an unknown or already revoked token means the user is logged out
    token = await find_refresh_token(session, data.refresh_token)
    if token is not None and token.revoked_at is None:
        await revoke_refresh_token(session, token)
    await session.commit()
