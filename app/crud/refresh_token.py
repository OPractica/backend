from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.models.database import RefreshToken


async def create_refresh_token(
    session: AsyncSession, user_id: int, family_id: UUID | None = None
) -> str:
    # No family means a new login session; a refresh passes its family on
    token = generate_refresh_token()
    hash_token = hash_refresh_token(token)
    refresh_token = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid4(),
        token_hash=hash_token,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    session.add(refresh_token)
    await session.flush()
    return token


async def find_refresh_token(
    session: AsyncSession, refresh_token: str
) -> RefreshToken | None:
    # Returns revoked and expired tokens too, so the caller can detect reuse
    hash_token = hash_refresh_token(refresh_token)
    query = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token)
        .with_for_update()
    )
    token = await session.scalar(query)
    return token


async def revoke_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    await session.flush()


async def revoke_token_family(session: AsyncSession, family_id: UUID) -> None:
    query = (
        update(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
    await session.execute(query)
    await session.flush()
