from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.schemas import LoginIn, RefreshIn, RegisterIn, ResendIn, TokenOut, VerifyIn
from app.services import auth as svc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=202)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db)):
    await svc.start_signup(db, data)
    return {"message": "Confirmation code sent.", "expires_in": settings.code_ttl_minutes * 60}


@router.post("/resend", status_code=202)
async def resend(data: ResendIn, db: AsyncSession = Depends(get_db)):
    await svc.resend_code(db, data.email)
    return {"message": "A new code was sent."}


@router.post("/verify", response_model=TokenOut)
async def verify(data: VerifyIn, db: AsyncSession = Depends(get_db)):
    return await svc.confirm_signup(db, data.email, data.code)


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    return await svc.login(db, data.email, data.password)


@router.post("/refresh", response_model=TokenOut)
async def refresh(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    return await svc.refresh(db, data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    await svc.logout(db, data.refresh_token)
