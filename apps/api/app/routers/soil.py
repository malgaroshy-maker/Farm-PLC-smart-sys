"""Soil moisture (Milestone G7): crop levels, soil probes, live status, and the gateway's
ingest endpoint. Values shown to people are % of available water (see services/soil.py)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import get_db
from app.deps import Actor, get_actor, require_admin, require_service
from app.models.sensor import Sensor
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.schemas.state import StateSyncPayload
from app.services import soil
from app.services.events import log_event
from app.services.live_state import load_snapshots, upsert_snapshots
from app.services.realtime import manager

router = APIRouter(tags=["Soil"])


class LevelOut(BaseModel):
    crop_type: str
    start_pct: float
    stop_pct: float
    confirmed: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LevelIn(BaseModel):
    start_pct: float = Field(ge=0, le=100)
    stop_pct: float = Field(ge=0, le=100)
    confirmed: bool


class ProbeIn(BaseModel):
    external_id: str = Field(min_length=3, max_length=64)
    zone_id: str
    depth_cm: int = Field(ge=5, le=200)


class ProbeOut(BaseModel):
    id: str
    external_id: str | None
    zone_id: str | None
    depth_cm: int | None
    enabled: bool

    model_config = {"from_attributes": True}


class SoilReading(BaseModel):
    """What the gateway posts for one probe reading (decoded uplink)."""

    device_id: str = Field(description="Probe id as the gateway knows it, e.g. LoRaWAN DevEUI")
    vwc_pct: float | None = Field(
        default=None, ge=0, le=100, description="Volumetric water content %"
    )
    moisture_pct: float | None = Field(
        default=None, ge=0, le=120, description="Already % of available water"
    )
    temperature_c: float | None = None
    ec_us_cm: float | None = None
    battery_pct: float | None = None


@router.get("/soil/levels", response_model=list[LevelOut])
async def get_levels(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    return sorted((await soil.levels(db)).values(), key=lambda r: r.crop_type)


@router.put("/soil/levels/{crop_type}", response_model=LevelOut)
async def put_level(
    crop_type: str,
    body: LevelIn,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.start_pct >= body.stop_pct:
        raise HTTPException(422, "start_pct must be below stop_pct")
    row = (await soil.levels(db)).get(crop_type)
    if row is None:
        raise HTTPException(404, f"Unknown crop '{crop_type}'")
    row.start_pct, row.stop_pct, row.confirmed = body.start_pct, body.stop_pct, body.confirmed
    row.updated_at, row.updated_by = clock.farm_now(), actor.actor_id
    await log_event(
        db,
        "soil.levels_changed",
        "crop",
        crop_type,
        actor_type="user",
        actor_id=actor.actor_id,
        payload=body.model_dump(),
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/soil/status")
async def get_status(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    status = await soil.soil_status(db, await load_snapshots(db))
    return [
        {
            "zone_id": s.zone_id,
            "moisture_pct": s.moisture,
            "source": s.source,
            "start_pct": s.start,
            "stop_pct": s.stop,
            "confirmed": s.confirmed,
            "state": s.state,
        }
        for s in status.values()
    ]


@router.get("/soil/probes", response_model=list[ProbeOut])
async def list_probes(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    q = (
        select(Sensor)
        .where(Sensor.external_id.is_not(None))
        .order_by(Sensor.zone_id, Sensor.depth_cm)
    )
    return (await db.execute(q)).scalars().all()


@router.post("/soil/probes", response_model=ProbeOut, status_code=201)
async def add_probe(
    body: ProbeIn, actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    zone = await db.get(Zone, body.zone_id)
    if zone is None:
        raise HTTPException(404, "Zone not found")
    ext = body.external_id.strip().upper()
    if (await db.execute(select(Sensor).where(Sensor.external_id == ext))).scalar_one_or_none():
        raise HTTPException(409, "A probe with this id is already registered")
    n = len((await db.execute(select(Sensor).where(Sensor.zone_id == zone.id))).scalars().all()) + 1
    probe = Sensor(
        id=f"sensor_probe_{zone.code.lower()}_{n}",
        farm_id=zone.farm_id,
        zone_id=zone.id,
        code=f"PRB_{zone.code}_{n}"[:30],
        sensor_type="soil_probe",  # not simulated: readings arrive through /ingest/soil
        unit="%",
        location_scope="zone",
        enabled=True,
        external_id=ext,
        depth_cm=body.depth_cm,
    )
    db.add(probe)
    await log_event(
        db,
        "soil.probe_added",
        "sensor",
        probe.id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload=body.model_dump(),
    )
    await db.commit()
    await db.refresh(probe)
    return probe


@router.delete("/soil/probes/{sensor_id}", status_code=204)
async def disable_probe(
    sensor_id: str, actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    probe = await db.get(Sensor, sensor_id)
    if probe is None or probe.external_id is None:
        raise HTTPException(404, "Probe not found")
    probe.enabled = False  # keep its history; it simply stops counting
    await log_event(
        db, "soil.probe_disabled", "sensor", probe.id, actor_type="user", actor_id=actor.actor_id
    )
    await db.commit()


@router.post("/ingest/soil")
async def ingest_soil(
    body: SoilReading, _: Actor = Depends(require_service), db: AsyncSession = Depends(get_db)
):
    """The farm gateway posts each probe reading here (LoRaWAN HTTP forwarding or the PLC bridge)."""
    probe = (
        await db.execute(select(Sensor).where(Sensor.external_id == body.device_id.strip().upper()))
    ).scalar_one_or_none()
    if probe is None or not probe.enabled or not probe.zone_id:
        raise HTTPException(
            404, f"Unknown or disabled probe '{body.device_id}' (register it in Settings)"
        )
    zone = await db.get(Zone, probe.zone_id)
    if body.vwc_pct is not None:
        value = soil.relative(body.vwc_pct, zone.soil_fc_vwc, zone.soil_wp_vwc)
    elif body.moisture_pct is not None:
        value = round(body.moisture_pct, 1)
    else:
        raise HTTPException(422, "Send vwc_pct or moisture_pct")
    now = utcnow()
    state = {
        "sensor_id": probe.id,
        "metric_key": f"moisture:{probe.zone_id}",
        "value": value,
        "unit": "%",
        "quality": "good",
        "timestamp": now.isoformat(),
        "external": True,
        "zone_id": probe.zone_id,
        "depth_cm": probe.depth_cm,
        "vwc_pct": body.vwc_pct,
        "temperature_c": body.temperature_c,
        "ec_us_cm": body.ec_us_cm,
        "battery_pct": body.battery_pct,
    }
    await upsert_snapshots(
        db,
        await load_snapshots(db),
        [StateSyncPayload(device_key=f"sensor_{probe.id}", state_json=state, updated_at=now)],
    )
    db.add(
        TelemetryPoint(
            metric_key="probe.moisture_pct",
            farm_id=probe.farm_id,
            zone_id=probe.zone_id,
            ts=clock.farm_now(),
            value_numeric=value,
        )
    )
    await db.commit()
    await manager.broadcast(
        "soil.reading", {"zone_id": probe.zone_id, "sensor_id": probe.id, "moisture_pct": value}
    )
    return {"zone_id": probe.zone_id, "moisture_pct": value}
