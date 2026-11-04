from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.models.database import RefreshToken


async def create_refresh_token(session: AsyncSession, user_id: int) -> str:
    token = generate_refresh_token()
    hash_token = hash_refresh_token(token)
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    session.add(refresh_token)
    await session.flush()
    return token


async def find_refresh_token(
    session: AsyncSession, refresh_token: str
) -> RefreshToken | None:
    hash_token = hash_refresh_token(refresh_token)
    query = (
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token,
            RefreshToken.expires_at > func.now(),
            RefreshToken.revoked_at.is_(None),
        )
        .with_for_update()
    )
    token = await session.scalar(query)
    return token


async def revoke_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    await session.flush()
