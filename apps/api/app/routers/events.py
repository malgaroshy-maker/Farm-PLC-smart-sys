"""Audit trail — /api/v1/events (append-only event_log, newest first)."""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import as_utc
from app.database import get_db
from app.deps import Actor, get_actor
from app.models.event_log import EventLog
from app.models.user import User

router = APIRouter(prefix="/events", tags=["Events"])


class EventResponse(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str | None
    actor_type: str
    actor_id: str | None
    actor_name: str | None
    payload: dict[str, Any] | None
    occurred_at: datetime


@router.get("", response_model=list[EventResponse])
async def list_events(
    limit: int = Query(100, ge=1, le=500),
    before_id: int | None = Query(None, description="Pagination: return events older than this id"),
    category: str | None = Query(
        None, description="Prefix filter, e.g. 'command', 'alarm', 'user'"
    ),
    entity_id: str | None = None,
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(EventLog, User.name)
        .outerjoin(User, User.id == EventLog.actor_id)
        .order_by(EventLog.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        q = q.where(EventLog.id < before_id)
    if category:
        q = q.where(EventLog.event_type.startswith(f"{category}."))
    if entity_id:
        q = q.where(EventLog.entity_id == entity_id)
    rows = (await db.execute(q)).all()
    return [
        EventResponse(
            id=e.id,
            event_type=e.event_type,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            actor_name=name,
            payload=json.loads(e.payload_json) if e.payload_json else None,
            occurred_at=as_utc(e.occurred_at),
        )
        for e, name in rows
    ]
