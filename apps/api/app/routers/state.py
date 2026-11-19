"""State endpoints — live map and sync /api/v1/state."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_service
from app.models.telemetry import DeviceStateSnapshot
from app.schemas.state import FarmMapState, StateSyncPayload
from app.services.alarms import engine as alarm_engine
from app.services.live_state import (
    current_map_state,
    diff_events,
    load_snapshots,
    upsert_snapshots,
)
from app.services.realtime import manager
from app.services.telemetry import recorder

router = APIRouter(prefix="/state", tags=["State"])


@router.get("/map", response_model=FarmMapState)
async def get_state_map(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """Current live state of the whole farm."""
    return await current_map_state(db)


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
        if event_type == "zone.state.changed":
            new_state = payload.get("current_state") or payload.get("state")
            if new_state in ("off", "completed", "faulted"):
                zid = payload.get("zone_id")
                if zid:
                    from app.services.cycles import record_cycle_end_for_zone

                    outcome = None
                    if new_state == "faulted":
                        outcome = "faulted"
                    elif new_state == "completed":
                        outcome = "completed"
                    await record_cycle_end_for_zone(db, zid, outcome=outcome)
                    await db.commit()
    after = await load_snapshots(db)
    await alarm_engine.on_state_sync(db, after)
    await recorder.maybe_record(db, after)
    await manager.broadcast("state.snapshot", await current_map_state(db))
    return {"success": True, "processed": len(payloads)}


@router.delete("/sync")
async def clear_state(_: Actor = Depends(require_service), db: AsyncSession = Depends(get_db)):
    """Clear the state cache (simulator reset)."""
    await db.execute(delete(DeviceStateSnapshot))
    return {"success": True}
