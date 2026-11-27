"""Auth endpoints — /api/v1/auth."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    password_problem,
    verify_password,
)
from app.database import get_db
from app.deps import Actor, require_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, PasswordChange, UserPublic
from app.services import login_throttle
from app.services.events import log_event
from app.services.realtime import manager

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    wait = login_throttle.retry_after(body.username)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again in a minute.",
            headers={"Retry-After": str(wait)},
        )
    result = await db.execute(
        select(User).where(func.lower(User.username) == body.username.strip().lower())
    )
    user = result.scalars().first()
    if not user or not user.is_active:
        burn_password_check(body.password)
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        # the typed name is not stored: people sometimes type a password into that box
        await log_event(
            db, "user.login_failed", "user", user.id if user else None, actor_type="system"
        )
        await db.commit()  # get_db rolls back when the request raises
        raise HTTPException(status_code=401, detail="Invalid username or password")
    login_throttle.clear(body.username)
    await log_event(db, "user.login", "user", user.id, actor_type="user", actor_id=user.id)
    return LoginResponse(
        access_token=create_access_token(user.id, user.role, user.token_version or 0),
        user=UserPublic.model_validate(user),
    )


@router.post("/password", response_model=LoginResponse)
async def change_own_password(
    body: PasswordChange,
    actor: Actor = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Change your own password. Every other sign-in of this user ends."""
    key = f"password:{actor.actor_id}"
    wait = login_throttle.retry_after(key)
    if wait:
        raise HTTPException(
            429, "Too many wrong passwords. Try again in a minute.", {"Retry-After": str(wait)}
        )
    user = await db.get(User, actor.actor_id)
    if not verify_password(body.current_password, user.password_hash):
        # 400, not 401: the session itself is fine
        raise HTTPException(400, "wrong_current_password")
    login_throttle.clear(key)
    problem = password_problem(body.new_password)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    await log_event(
        db, "user.password_changed", "user", user.id, actor_type="user", actor_id=user.id
    )
    await db.commit()
    await manager.close_user(user.id)
    return LoginResponse(
        access_token=create_access_token(user.id, user.role, user.token_version),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(actor: Actor = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await db.get(User, actor.actor_id)
