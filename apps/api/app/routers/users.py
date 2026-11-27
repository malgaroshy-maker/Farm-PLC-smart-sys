"""User accounts — /api/v1/users. Admin only. Accounts are switched off, never deleted."""

import asyncio
import re
from uuid import uuid4
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, password_problem
from app.database import get_db
from app.deps import Actor, require_admin
from app.models.notification import PushSubscription
from app.models.user import User
from app.schemas.auth import UserAdminView, UserCreate, UserUpdate
from app.services.events import log_event
from app.services.realtime import manager

router = APIRouter(prefix="/users", tags=["Users"])

USERNAME = re.compile(r"[a-z0-9._-]{3,50}")

# "is there still another admin?" and the change must not interleave between two requests
_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


def _turn() -> asyncio.Lock:
    return _locks.setdefault(asyncio.get_running_loop(), asyncio.Lock())


async def _free_username(db: AsyncSession, wanted: str, own_id: str | None = None) -> str:
    name = wanted.strip().lower()
    if not USERNAME.fullmatch(name):
        raise HTTPException(422, "username_invalid")
    taken = await db.scalar(select(User.id).where(func.lower(User.username) == name))
    if taken and taken != own_id:
        raise HTTPException(409, "username_taken")
    return name


def _checked_password(password: str) -> str:
    problem = password_problem(password)
    if problem:
        raise HTTPException(422, problem)
    return hash_password(password)


@router.get("", response_model=list[UserAdminView])
async def list_users(_: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(User).order_by(User.created_at, User.username)))


@router.post("", response_model=UserAdminView, status_code=201)
async def create_user(
    body: UserCreate, actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    async with _turn():
        if not body.name.strip():
            raise HTTPException(422, "name_required")
        user = User(
            id=f"user_{uuid4().hex[:12]}",
            username=await _free_username(db, body.username),
            name=body.name.strip(),
            role=body.role,
            is_active=True,
            token_version=0,
            password_hash=_checked_password(body.password),
        )
        db.add(user)
        await log_event(
            db,
            "user.created",
            "user",
            user.id,
            actor_type="user",
            actor_id=actor.actor_id,
            payload={"role": user.role},
        )
        await db.commit()
    return user


@router.patch("/{user_id}", response_model=UserAdminView)
async def update_user(
    user_id: str,
    body: UserUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    async with _turn():
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(404, "user_not_found")
        role = body.role or user.role
        active = user.is_active if body.is_active is None else body.is_active
        if user.role == "owner_admin" and user.is_active and (role != "owner_admin" or not active):
            others = await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == "owner_admin", User.is_active.is_(True), User.id != user.id)
            )
            if not others:
                raise HTTPException(409, "last_admin")
        changed = []
        if body.name is not None and body.name.strip() and body.name.strip() != user.name:
            user.name = body.name.strip()
            changed.append("name")
        if body.username is not None and body.username.strip().lower() != user.username.lower():
            user.username = await _free_username(db, body.username, user.id)
            changed.append("username")
        if body.password:
            user.password_hash = _checked_password(body.password)
            changed.append("password")
        if role != user.role:
            user.role = role
            changed.append("role")
        if active != user.is_active:
            user.is_active = active
            changed.append("active")
        sign_out = bool({"password", "role", "active"} & set(changed))
        if sign_out:
            user.token_version = (user.token_version or 0) + 1
        if not user.is_active or "password" in changed:
            # their phones must stop receiving the farm's alarms
            await db.execute(delete(PushSubscription).where(PushSubscription.user_id == user.id))
        if changed:
            await log_event(
                db,
                "user.updated",
                "user",
                user.id,
                actor_type="user",
                actor_id=actor.actor_id,
                payload={"changed": changed, "role": user.role, "active": user.is_active},
            )
        await db.commit()
    if sign_out:
        await manager.close_user(user.id)
    return user
