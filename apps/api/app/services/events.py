"""Append-only audit trail helper."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.models.event_log import EventLog


async def log_event(
    db: AsyncSession,
    event_type: str,
    entity_type: str,
    entity_id: str | None,
    *,
    actor_type: str,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        EventLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            payload_json=json.dumps(payload, default=str) if payload else None,
            occurred_at=utcnow(),
        )
    )
