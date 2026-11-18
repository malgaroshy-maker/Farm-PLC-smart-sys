"""Authentication / authorization dependencies."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, is_service_token
from app.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Actor:
    """Who is calling: a logged-in user or the simulator/PLC bridge service."""

    actor_type: str  # "user" | "plc"
    actor_id: str | None
    role: str  # user role, or "service"
    name: str = ""

    @property
    def is_service(self) -> bool:
        return self.role == "service"


SERVICE_ACTOR = Actor(actor_type="plc", actor_id=None, role="service", name="simulator")

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def resolve_token(token: str, db: AsyncSession) -> Actor | None:
    if is_service_token(token):
        return SERVICE_ACTOR
    claims = decode_access_token(token)
    if not claims:
        return None
    user = await db.get(User, claims.get("sub"))
    if not user or not user.is_active:
        return None
    return Actor(actor_type="user", actor_id=user.id, role=user.role, name=user.name)


async def get_actor(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Actor:
    if creds is None:
        raise _unauthorized
    actor = await resolve_token(creds.credentials, db)
    if actor is None:
        raise _unauthorized
    return actor


def require_roles(*roles: str):
    """Allow only users with one of the given roles (service token is rejected)."""

    async def dep(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.is_service or actor.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return actor

    return dep


async def require_user(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.is_service:
        raise HTTPException(status_code=403, detail="User login required")
    return actor


async def require_service(actor: Actor = Depends(get_actor)) -> Actor:
    if not actor.is_service:
        raise HTTPException(status_code=403, detail="Service token required")
    return actor


require_admin = require_roles("owner_admin")


async def require_admin_or_service(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.is_service or actor.role == "owner_admin":
        return actor
    raise HTTPException(status_code=403, detail="Insufficient permissions")

