from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.database import User
from app.schemas.schemas import UserCreate


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email.lower())

    result = await session.scalar(query)

    return result


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    query = select(User).where(User.id == user_id)

    result = await session.scalar(query)

    return result
