"""Password hashing (bcrypt) and JWT access tokens."""

import hmac
from datetime import timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.timeutil import utcnow

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_hash.startswith("$2"):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: str, role: str) -> str:
    expire = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire}, settings.secret_key, algorithm=ALGORITHM
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def is_service_token(token: str) -> bool:
    return hmac.compare_digest(token.encode(), settings.simulator_token.encode())
