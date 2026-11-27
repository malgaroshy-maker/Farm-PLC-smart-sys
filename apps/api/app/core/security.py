"""Password hashing (bcrypt) and JWT access tokens."""

import hmac
from datetime import timedelta

import bcrypt
import jwt

from app.config import settings
from app.core.timeutil import utcnow

ALGORITHM = "HS256"


# bcrypt reads only the first 72 bytes (an Arabic letter takes 2)
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_CHARS = 8


def password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_CHARS:
        return "password_too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "password_too_long"
    return None


# checked when the username does not exist, so both answers take the same time
_NOBODY_HASH = bcrypt.hashpw(b"no such user", bcrypt.gensalt()).decode("ascii")


def burn_password_check(password: str) -> None:
    verify_password(password, _NOBODY_HASH)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_hash.startswith("$2"):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: str, role: str, version: int = 0) -> str:
    expire = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "ver": version, "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def is_service_token(token: str) -> bool:
    return hmac.compare_digest(token.encode(), settings.simulator_token.encode())
