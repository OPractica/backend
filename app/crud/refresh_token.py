from datetime import UTC, datetime, timedelta

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
