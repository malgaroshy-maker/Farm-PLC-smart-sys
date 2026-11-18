"""Auth endpoints — /api/v1/auth."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.deps import Actor, require_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserPublic
from app.services.events import log_event

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    await log_event(db, "user.login", "user", user.id, actor_type="user", actor_id=user.id)
    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(actor: Actor = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await db.get(User, actor.actor_id)
