from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db import get_db
from app.models import DEFAULT_SETTINGS, User
from app.schemas import UserOut, UserPatch

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        user.phone = data.phone
    if data.settings is not None:
        user.settings = {**DEFAULT_SETTINGS, **(user.settings or {}), **data.settings.model_dump(exclude_none=True)}
    await db.commit()
    return user
