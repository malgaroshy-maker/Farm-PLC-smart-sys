"""Device endpoints — Pumps, Valves, Sensors."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_admin
from app.models.pump import Pump
from app.models.sensor import Sensor
from app.models.valve import Valve
from app.schemas.device import (
    PumpResponse,
    PumpUpdate,
    SensorResponse,
    SensorUpdate,
    ValveResponse,
    ValveUpdate,
)
from app.services.events import log_event

router = APIRouter(tags=["Devices"])


# ── Pumps ────────────────────────────────────────────────


@router.get("/pumps", response_model=list[PumpResponse])
async def list_pumps(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """List all pumps."""
    result = await db.execute(select(Pump))
    return result.scalars().all()


@router.patch("/pumps/{pump_id}", response_model=PumpResponse)
async def update_pump(
    pump_id: str,
    update: PumpUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update pump configuration."""
    pump = await db.get(Pump, pump_id)
    if not pump:
        raise HTTPException(status_code=404, detail=f"Pump '{pump_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(pump, field, value)
    await log_event(
        db,
        "device.changed",
        "pump",
        pump_id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"changed": sorted(update.model_dump(exclude_unset=True))},
    )
    await db.flush()
    await db.refresh(pump)
    return pump


# ── Valves ───────────────────────────────────────────────


@router.get("/valves", response_model=list[ValveResponse])
async def list_valves(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """List all valves."""
    result = await db.execute(select(Valve))
    return result.scalars().all()


@router.patch("/valves/{valve_id}", response_model=ValveResponse)
async def update_valve(
    valve_id: str,
    update: ValveUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update valve configuration."""
    valve = await db.get(Valve, valve_id)
    if not valve:
        raise HTTPException(status_code=404, detail=f"Valve '{valve_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(valve, field, value)
    await log_event(
        db,
        "device.changed",
        "valve",
        valve_id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"changed": sorted(update.model_dump(exclude_unset=True))},
    )
    await db.flush()
    await db.refresh(valve)
    return valve


# ── Sensors ──────────────────────────────────────────────


@router.get("/sensors", response_model=list[SensorResponse])
async def list_sensors(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """List all sensors."""
    result = await db.execute(select(Sensor))
    return result.scalars().all()


@router.patch("/sensors/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: str,
    update: SensorUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update sensor configuration."""
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(sensor, field, value)
    await log_event(
        db,
        "device.changed",
        "sensor",
        sensor_id,
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"changed": sorted(update.model_dump(exclude_unset=True))},
    )
    await db.flush()
    await db.refresh(sensor)
    return sensor
