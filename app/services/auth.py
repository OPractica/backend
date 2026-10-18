from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as sec
from app.core.config import settings
from app.models import PendingSignup, RefreshToken, User
from app.schemas import RegisterIn, TokenOut
from app.services import mail
from app.utils import now, utc


async def _send_code(email: str, code: str) -> None:
    try:
        await mail.send_mail(email, *mail.code_email(code), strict=True)
    except Exception as err:
        raise HTTPException(503, "Could not send the email. Try again later.") from err


async def start_signup(db: AsyncSession, data: RegisterIn) -> None:
    if await db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "An account with this email already exists.")
    code = sec.new_code()
    p = await db.get(PendingSignup, data.email) or PendingSignup(email=data.email)
    p.full_name, p.phone = data.full_name.strip(), data.phone
    p.password_hash = sec.hash_password(data.password)
    p.code_hash = sec.hash_code(data.email, code)
    p.expires_at = now() + timedelta(minutes=settings.code_ttl_minutes)
    p.sent_at, p.attempts = now(), 0
    db.add(p)
    await db.commit()
    await _send_code(data.email, code)


async def resend_code(db: AsyncSession, email: str) -> None:
    p = await db.get(PendingSignup, email)
    if not p:
        raise HTTPException(400, "No pending registration. Register again.")
    if (now() - utc(p.sent_at)).total_seconds() < 30:
        raise HTTPException(429, "Please wait a few seconds before asking for a new code.")
    code = sec.new_code()
    p.code_hash, p.sent_at, p.attempts = sec.hash_code(email, code), now(), 0
    p.expires_at = now() + timedelta(minutes=settings.code_ttl_minutes)
    await db.commit()
    await _send_code(email, code)


async def issue_tokens(db: AsyncSession, user: User) -> TokenOut:
    refresh = sec.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sec.hash_token(refresh),
            expires_at=now() + timedelta(days=settings.refresh_days),
        )
    )
    await db.commit()
    return TokenOut(access_token=sec.create_access_token(user.id), refresh_token=refresh)


async def confirm_signup(db: AsyncSession, email: str, code: str) -> TokenOut:
    p = await db.get(PendingSignup, email)
    if not p:
        raise HTTPException(400, "No pending registration. Register again.")
    if now() > utc(p.expires_at):
        raise HTTPException(400, "Code expired. Send a new code.")
    if p.attempts >= 5:
        raise HTTPException(429, "Too many attempts. Send a new code.")
    if not sec.hmac.compare_digest(p.code_hash, sec.hash_code(email, code)):
        p.attempts += 1
        await db.commit()
        raise HTTPException(400, "Wrong code.")
    user = User(email=email, full_name=p.full_name, phone=p.phone, password_hash=p.password_hash)
    db.add(user)
    await db.delete(p)
    try:
        await db.commit()
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from err
    return await issue_tokens(db, user)


async def login(db: AsyncSession, email: str, password: str) -> TokenOut:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not sec.verify_password(password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    return await issue_tokens(db, user)


async def refresh(db: AsyncSession, token: str) -> TokenOut:
    rt = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sec.hash_token(token)))
    if not rt or rt.revoked or now() > utc(rt.expires_at):
        raise HTTPException(401, "Session expired. Please log in again.")
    user = await db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Session expired. Please log in again.")
    rt.revoked = True  # rotation: every refresh token works once
    return await issue_tokens(db, user)


async def logout(db: AsyncSession, token: str) -> None:
    rt = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sec.hash_token(token)))
    if rt:
        rt.revoked = True
        await db.commit()
