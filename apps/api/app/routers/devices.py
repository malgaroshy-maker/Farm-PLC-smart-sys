"""Device endpoints — Pumps, Valves, Sensors."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pump import Pump
from app.models.valve import Valve
from app.models.sensor import Sensor
from app.schemas.device import (
    PumpResponse,
    PumpUpdate,
    ValveResponse,
    ValveUpdate,
    SensorResponse,
    SensorUpdate,
)

router = APIRouter(tags=["Devices"])


# ── Pumps ────────────────────────────────────────────────

@router.get("/pumps", response_model=list[PumpResponse])
async def list_pumps(db: AsyncSession = Depends(get_db)):
    """List all pumps."""
    result = await db.execute(select(Pump))
    return result.scalars().all()


@router.patch("/pumps/{pump_id}", response_model=PumpResponse)
async def update_pump(pump_id: str, update: PumpUpdate, db: AsyncSession = Depends(get_db)):
    """Update pump configuration."""
    pump = await db.get(Pump, pump_id)
    if not pump:
        raise HTTPException(status_code=404, detail=f"Pump '{pump_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(pump, field, value)
    await db.flush()
    await db.refresh(pump)
    return pump


# ── Valves ───────────────────────────────────────────────

@router.get("/valves", response_model=list[ValveResponse])
async def list_valves(db: AsyncSession = Depends(get_db)):
    """List all valves."""
    result = await db.execute(select(Valve))
    return result.scalars().all()


@router.patch("/valves/{valve_id}", response_model=ValveResponse)
async def update_valve(valve_id: str, update: ValveUpdate, db: AsyncSession = Depends(get_db)):
    """Update valve configuration."""
    valve = await db.get(Valve, valve_id)
    if not valve:
        raise HTTPException(status_code=404, detail=f"Valve '{valve_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(valve, field, value)
    await db.flush()
    await db.refresh(valve)
    return valve


# ── Sensors ──────────────────────────────────────────────

@router.get("/sensors", response_model=list[SensorResponse])
async def list_sensors(db: AsyncSession = Depends(get_db)):
    """List all sensors."""
    result = await db.execute(select(Sensor))
    return result.scalars().all()


@router.patch("/sensors/{sensor_id}", response_model=SensorResponse)
async def update_sensor(sensor_id: str, update: SensorUpdate, db: AsyncSession = Depends(get_db)):
    """Update sensor configuration."""
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_id}' not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(sensor, field, value)
    await db.flush()
    await db.refresh(sensor)
    return sensor
