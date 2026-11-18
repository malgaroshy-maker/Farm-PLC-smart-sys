"""State endpoints — live map and sync /api/v1/state."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_service
from app.models.telemetry import DeviceStateSnapshot
from app.schemas.state import FarmMapState, StateSyncPayload
from app.services.live_state import (
    build_map_state,
    diff_events,
    load_snapshots,
    upsert_snapshots,
)
from app.services.realtime import manager

router = APIRouter(prefix="/state", tags=["State"])


@router.get("/map", response_model=FarmMapState)
async def get_state_map(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """Current live state of the whole farm."""
    return build_map_state(await load_snapshots(db))


@router.post("/sync")
async def sync_state(
    payloads: list[StateSyncPayload],
    _: Actor = Depends(require_service),
    db: AsyncSession = Depends(get_db),
):
    """Simulator/PLC bridge pushes batch state; changes are broadcast over WebSocket."""
    before = await load_snapshots(db)
    await upsert_snapshots(db, before, payloads)
    await db.commit()

    for event_type, payload in diff_events(before, payloads):
        await manager.broadcast(event_type, payload)
    await manager.broadcast("state.snapshot", build_map_state(await load_snapshots(db)))
    return {"success": True, "processed": len(payloads)}


@router.delete("/sync")
async def clear_state(_: Actor = Depends(require_service), db: AsyncSession = Depends(get_db)):
    """Clear the state cache (simulator reset)."""
    await db.execute(delete(DeviceStateSnapshot))
    return {"success": True}
