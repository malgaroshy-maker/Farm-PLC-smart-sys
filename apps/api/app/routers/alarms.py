"""Alarm endpoints — /api/v1/alarms."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_roles
from app.models.alarm import Alarm
from app.schemas.alarm import AlarmResponse
from app.services.alarms import active_alarm_responses, to_response
from app.services.alarms import engine as alarm_engine

router = APIRouter(prefix="/alarms", tags=["Alarms"])


@router.get("", response_model=list[AlarmResponse])
async def list_alarms(
    view: Literal["active", "history"] = "active",
    limit: int = Query(100, ge=1, le=500),
    zone_id: str | None = None,
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """`active` = open alarms (incl. latched), most severe first; `history` = newest first."""
    if view == "active":
        alarms = await active_alarm_responses(db)
        return [a for a in alarms if zone_id is None or a.zone_id == zone_id]
    q = select(Alarm).order_by(Alarm.triggered_at.desc()).limit(limit)
    if zone_id:
        q = q.where(Alarm.zone_id == zone_id)
    return [to_response(a) for a in (await db.execute(q)).scalars()]


@router.get("/{alarm_id}", response_model=AlarmResponse)
async def get_alarm(
    alarm_id: str, _: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
):
    alarm = await db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(404, "Alarm not found")
    return to_response(alarm)


@router.post("/{alarm_id}/ack", response_model=AlarmResponse)
async def acknowledge_alarm(
    alarm_id: str,
    actor: Actor = Depends(require_roles("owner_admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge: someone has seen it. Does not clear the condition (ALARM_MATRIX §11)."""
    return to_response(await alarm_engine.acknowledge(db, alarm_id, actor))


@router.post("/{alarm_id}/reset", response_model=AlarmResponse)
async def reset_alarm(
    alarm_id: str,
    actor: Actor = Depends(require_roles("owner_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Reset a latched alarm after its condition has returned to normal."""
    return to_response(await alarm_engine.reset(db, alarm_id, actor))
