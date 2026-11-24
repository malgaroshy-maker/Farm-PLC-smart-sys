"""Zone endpoints — CRUD /api/v1/zones."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_admin, require_roles
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate
from app.services.alarms import MAINTENANCE_DONE
from app.services.events import log_event

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get("", response_model=list[ZoneResponse])
async def list_zones(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """List all zones."""
    result = await db.execute(select(Zone).order_by(Zone.priority))
    return result.scalars().all()


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: str, _: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """Get zone by ID."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    return zone


def _check_ranges(zone: Zone) -> None:
    if zone.flow_min_m3h > zone.flow_max_m3h:
        raise HTTPException(422, "flow_min_m3h must not exceed flow_max_m3h")
    if zone.pressure_min_bar > zone.pressure_max_bar:
        raise HTTPException(422, "pressure_min_bar must not exceed pressure_max_bar")
    if (
        zone.moisture_start_pct is not None
        and zone.moisture_stop_pct is not None
        and zone.moisture_start_pct >= zone.moisture_stop_pct
    ):
        raise HTTPException(422, "moisture_start_pct must be below moisture_stop_pct")
    if (
        zone.soil_fc_vwc is not None
        and zone.soil_wp_vwc is not None
        and zone.soil_wp_vwc >= zone.soil_fc_vwc
    ):
        raise HTTPException(422, "soil_wp_vwc must be below soil_fc_vwc")
    if zone.default_duration_min > zone.max_runtime_min:
        raise HTTPException(422, "default_duration_min must not exceed max_runtime_min")


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    update: ZoneUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Partially update zone configuration (disable instead of delete: history stays)."""
    from app.models.valve import Valve
    from app.services.realtime import manager

    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)
    _check_ranges(zone)
    if "enabled" in update_data:  # the zone's valve follows the zone
        for v in (await db.execute(select(Valve).where(Valve.zone_id == zone.id))).scalars():
            v.enabled = zone.enabled

    await log_event(
        db,
        "zone.updated",
        "zone",
        zone.id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload=update_data,
    )
    await db.commit()
    await db.refresh(zone)
    await manager.broadcast("zones.updated", {"zone_id": zone.id})
    return zone


@router.post("", response_model=ZoneResponse, status_code=201)
async def create_zone(
    body: ZoneCreate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a zone with its valve and moisture sensor (owner, G3).

    The controller (simulator now, PLC later) picks it up on its next start; the map shows
    it once its outline is traced (tools/map-geometry).
    """
    from app.config import settings
    from app.models.sensor import Sensor
    from app.models.valve import Valve
    from app.services.realtime import manager

    zid = f"zone_{body.code.lower()}"
    if (
        await db.get(Zone, zid)
        or (await db.execute(select(Zone).where(Zone.code == body.code))).first()
    ):
        raise HTTPException(409, f"zone code '{body.code}' already exists")
    max_prio = (
        await db.execute(select(Zone.priority).order_by(Zone.priority.desc()))
    ).scalars().first() or 0
    zone = Zone(
        id=zid,
        farm_id=settings.farm_id,
        enabled=True,
        priority=min(99, max_prio + 1),
        source_preference="tank",
        allows_direct_well=False,
        **body.model_dump(),
    )
    _check_ranges(zone)
    db.add(zone)
    db.add(
        Valve(
            id=f"valve_{body.code.lower()}",
            zone_id=zid,
            code=f"VALVE_{body.code}",
            enabled=True,
            has_open_feedback=True,
            has_close_feedback=True,
        )
    )
    db.add(
        Sensor(
            id=f"sensor_moisture_{body.code.lower()}",
            farm_id=settings.farm_id,
            zone_id=zid,
            code=f"MOISTURE_{body.code}",
            sensor_type="moisture",
            unit="%",
            location_scope="zone",
            enabled=True,
        )
    )
    await log_event(
        db,
        "zone.created",
        "zone",
        zid,
        actor_type="user",
        actor_id=actor.actor_id,
        payload=body.model_dump(),
    )
    await db.commit()
    await db.refresh(zone)
    await manager.broadcast("zones.updated", {"zone_id": zid})
    return zone


class MaintenanceDone(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/{zone_id}/maintenance-done", status_code=204)
async def maintenance_done(
    zone_id: str,
    body: MaintenanceDone | None = None,
    actor: Actor = Depends(require_roles("owner_admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Record that the zone was inspected/repaired.

    Faults before this moment no longer count towards ALM-036 (repeated faults),
    so the maintenance alarm clears on the next state sync.
    """
    if not await db.get(Zone, zone_id):
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    await log_event(
        db,
        MAINTENANCE_DONE,
        "zone",
        zone_id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"note": body.note} if body and body.note else None,
    )
