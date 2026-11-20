from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser
from app.api.errors import APIError
from app.api.openapi import AUTH_RESPONSES, error_response, example_response
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


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user",
    description="Creates an employee account. The email must not be registered yet.",
    responses={
        201: example_response(
            "The user was created",
            {
                "id": 1,
                "email": "anna@example.com",
                "full_name": "Anna Smith",
                "role": "employee",
                "is_active": True,
            },
        ),
        409: error_response(
            "The email is already registered",
            "email is already in use",
            "email_taken",
        ),
    },
)
async def register(
    session: SessionDep,
    data: Annotated[
        UserCreate,
        Body(
            openapi_examples={
                "employee": {
                    "summary": "New employee",
                    "value": {
                        "email": "anna@example.com",
                        "password": "S3cure-pass!",
                        "full_name": "Anna Smith",
                    },
                }
            }
        ),
    ],
):
    existing = await get_user_by_email(session, data.email)

    if existing:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="email is already in use",
            code="email_taken",
        )

    try:
        user = await create_user(session, data)
    except IntegrityError:
        await session.rollback()
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            detail="email is already in use",
            code="email_taken",
        )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description=(
        "Checks the email and password and returns an access token (15 minutes) "
        "and a refresh token (7 days)."
    ),
    responses={
        200: example_response(
            "A new token pair",
            {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.signature",
                "refresh_token": "d1f0c2a8b7e94c5f8a3b6d2e9c4a1f70",
                "token_type": "bearer",
            },
        ),
        401: error_response(
            "Wrong email or password",
            "invalid email or password",
            "invalid_credentials",
        ),
        403: error_response(
            "The user is deactivated", "user is not active", "user_inactive"
        ),
    },
)
async def login(
    session: SessionDep,
    data: Annotated[
        UserLogin,
        Body(
            openapi_examples={
                "employee": {
                    "summary": "Employee credentials",
                    "value": {"email": "anna@example.com", "password": "S3cure-pass!"},
                }
            }
        ),
    ],
) -> TokenResponse:
    user = await get_user_by_email(session, data.email)

    if not user or not verify_password(data.password, user.password_hash):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
            code="invalid_credentials",
        )

    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not active",
            code="user_inactive",
        )
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(session, user.id)
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user",
    description="Returns the profile of the user who owns the access token.",
    responses={
        200: example_response(
            "The current user",
            {
                "id": 1,
                "email": "anna@example.com",
                "full_name": "Anna Smith",
                "role": "employee",
                "is_active": True,
            },
        ),
        **AUTH_RESPONSES,
    },
)
async def me(user: CurrentUser) -> UserResponse:
    return user


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh the token pair",
    description=(
        "Exchanges a refresh token for a new token pair. A refresh token works only "
        "once: save the new one. Reusing an old token revokes the whole login session."
    ),
    responses={
        200: example_response(
            "A new token pair",
            {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.signature",
                "refresh_token": "d1f0c2a8b7e94c5f8a3b6d2e9c4a1f70",
                "token_type": "bearer",
            },
        ),
        401: error_response(
            "The refresh token is unknown, expired, revoked or already used",
            "invalid refresh token",
            "invalid_refresh_token",
        ),
    },
)
async def refresh(
    session: SessionDep,
    data: Annotated[
        RefreshRequest,
        Body(
            openapi_examples={
                "refresh": {
                    "summary": "Refresh token from login",
                    "value": {"refresh_token": "d1f0c2a8b7e94c5f8a3b6d2e9c4a1f70"},
                }
            }
        ),
    ],
) -> TokenResponse:
    token = await find_refresh_token(session, data.refresh_token)
    if token is None or token.expires_at <= datetime.now(UTC):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
            code="invalid_refresh_token",
        )
    if token.revoked_at is not None:
        # A rotated token came back: it may be stolen, so end the whole login
        # session. Commit before raising, otherwise the revoke is rolled back.
        await revoke_token_family(session, token.family_id)
        await session.commit()
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
            code="invalid_refresh_token",
        )
    await revoke_refresh_token(session, token)

    user = await get_user_by_id(session, token.user_id)
    if user is None or not user.is_active:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
            code="invalid_refresh_token",
        )
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(session, user.id, token.family_id)
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Log out",
    description=(
        "Revokes the refresh token. Always answers 204, even if the token is "
        "unknown or already revoked."
    ),
    responses={204: {"description": "The user is logged out"}},
)
async def logout(
    session: SessionDep,
    data: Annotated[
        RefreshRequest,
        Body(
            openapi_examples={
                "refresh": {
                    "summary": "Refresh token to revoke",
                    "value": {"refresh_token": "d1f0c2a8b7e94c5f8a3b6d2e9c4a1f70"},
                }
            }
        ),
    ],
) -> None:
    # Always 204: an unknown or already revoked token means the user is logged out
    token = await find_refresh_token(session, data.refresh_token)
    if token is not None and token.revoked_at is None:
        await revoke_refresh_token(session, token)
    await session.commit()
