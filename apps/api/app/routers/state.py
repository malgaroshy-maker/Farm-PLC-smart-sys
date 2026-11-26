"""State endpoints — live map and sync /api/v1/state."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ACTIVE_ZONE_STATES
from app.database import get_db
from app.deps import Actor, get_actor, require_service
from app.models.telemetry import DeviceStateSnapshot
from app.schemas.state import FarmMapState, StateSyncPayload
from app.services.alarms import engine as alarm_engine
from app.services.cycles import record_cycle_end_for_zone, record_unattended_cycle_start
from app.services.live_state import (
    current_map_state,
    diff_events,
    load_snapshots,
    upsert_snapshots,
)
from app.services.pump_history import record_pump_feedback
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
    accepted = await upsert_snapshots(db, payloads)
    if not accepted:
        return {"success": True, "processed": len(payloads), "accepted": 0}
    await record_pump_feedback(db, accepted)

    events = diff_events(before, accepted)
    run_sources = {p.device_key: p.state_json.get("run_source") for p in accepted}
    for event_type, payload in events:
        zone_id = payload.get("zone_id")
        if event_type != "zone.state.changed" or not zone_id:
            continue
        new_state = payload["current_state"]
        if new_state in ACTIVE_ZONE_STATES:
            run_source = run_sources.get(f"zone_{zone_id}")
            if run_source in ("panel", "fallback"):
                await record_unattended_cycle_start(db, zone_id, run_source)
        elif new_state in ("off", "completed", "faulted"):
            outcome = new_state if new_state != "off" else None
            await record_cycle_end_for_zone(db, zone_id, outcome=outcome)

    await db.commit()
    for event_type, payload in events:
        await manager.broadcast(event_type, payload)
    after = await load_snapshots(db)
    await alarm_engine.on_state_sync(db, after)
    await recorder.maybe_record(db, after)
    await manager.broadcast("state.snapshot", await current_map_state(db))
    return {"success": True, "processed": len(payloads), "accepted": len(accepted)}


@router.delete("/sync")
async def clear_state(_: Actor = Depends(require_service), db: AsyncSession = Depends(get_db)):
    """Clear the state cache (simulator reset)."""
    await db.execute(delete(DeviceStateSnapshot))
    return {"success": True}
