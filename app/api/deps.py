from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.errors import APIError
from app.core.db import SessionDep
from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.models.database import User

bearer_scheme = HTTPBearer()


def unauthorized(detail: str, code: str) -> APIError:
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        code=code,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise unauthorized("token expired", "token_expired") from None
    except jwt.InvalidTokenError:
        raise unauthorized("invalid token", "invalid_token") from None

    user = await get_user_by_id(session, user_id)
    if not user:
        raise unauthorized("invalid token", "invalid_token")
    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not active",
            code="user_inactive",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
