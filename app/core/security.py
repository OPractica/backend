import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(email: str, code: str) -> str:
    return hmac.new(settings.secret_key.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def create_access_token(user_id: str) -> str:
    exp = datetime.now(UTC) + timedelta(minutes=settings.access_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"]).get("sub")
    except jwt.PyJWTError:
        return None
