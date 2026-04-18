"""State endpoints — Live Map and Sync /api/v1/state."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import get_db
from app.models.telemetry import DeviceStateSnapshot
from app.schemas.state import FarmMapState, StateSyncPayload

router = APIRouter(prefix="/state", tags=["State"])


@router.get("/map", response_model=FarmMapState)
async def get_state_map(db: AsyncSession = Depends(get_db)):
    """Get the current live state of the entire farm simulation."""
    result = await db.execute(select(DeviceStateSnapshot))
    snapshots = result.scalars().all()
    
    # Initialize empty mappings
    system_mode = "off"
    zones = []
    pumps = []
    valves = []
    sensors = []
    tank_level_pct = 0.0
    main_pressure_bar = 0.0
    main_flow_m3h = 0.0
    active_alarms = []
    last_update = datetime.min
    
    # In SQLite, we rely on the device_key prefixes
    # system_mode
    # zone_<id>
    # pump_<id>
    # valve_<id>
    # sensor_<id>
    # simulation_stats
    
    for snap in snapshots:
        val = json.loads(snap.state_json)
        
        # update freshness
        if snap.updated_at.tzinfo is None:
            snap_time = snap.updated_at
        else:
            snap_time = snap.updated_at.replace(tzinfo=None)
            
        if snap_time > last_update:
            last_update = snap_time
            
        if snap.device_key == "system_mode":
            system_mode = val.get("mode", "off")
        elif snap.device_key.startswith("zone_"):
            zones.append(val)
        elif snap.device_key.startswith("pump_"):
            pumps.append(val)
        elif snap.device_key.startswith("valve_"):
            valves.append(val)
        elif snap.device_key.startswith("sensor_"):
            sensors.append(val)
        elif snap.device_key == "simulation_stats":
            tank_level_pct = val.get("tank_level_pct", 0.0)
            main_pressure_bar = val.get("main_pressure_bar", 0.0)
            main_flow_m3h = val.get("main_flow_m3h", 0.0)
            
    is_fresh = True
    now = datetime.utcnow()
    # If last update is older than 5 seconds, it's stale
    if (now - last_update).total_seconds() > 5.0 and len(snapshots) > 0:
        is_fresh = False
        
    return FarmMapState(
        system_mode=system_mode,
        zones=zones,
        pumps=pumps,
        valves=valves,
        sensors=sensors,
        tank_level_pct=tank_level_pct,
        main_pressure_bar=main_pressure_bar,
        main_flow_m3h=main_flow_m3h,
        active_alarms=active_alarms,
        data_fresh=is_fresh,
        last_snapshot_ts=last_update if last_update != datetime.min else now,
    )


@router.post("/sync")
async def sync_state(payloads: list[StateSyncPayload], db: AsyncSession = Depends(get_db)):
    """Simulator pushes batch state updates here."""
    # SQLite upsert
    for p in payloads:
        stmt = sqlite_insert(DeviceStateSnapshot).values(
            device_key=p.device_key,
            state_json=json.dumps(p.state_json),
            updated_at=p.updated_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['device_key'],
            set_={'state_json': stmt.excluded.state_json, 'updated_at': stmt.excluded.updated_at}
        )
        await db.execute(stmt)
        
    return {"success": True, "processed": len(payloads)}


@router.delete("/sync")
async def clear_state(db: AsyncSession = Depends(get_db)):
    """Clear all state cache (for reset)."""
    await db.execute(delete(DeviceStateSnapshot))
    return {"success": True}
