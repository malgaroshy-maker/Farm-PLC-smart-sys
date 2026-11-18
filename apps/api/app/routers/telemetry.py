"""Telemetry history — /api/v1/telemetry."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor
from app.services.telemetry import METRIC_KEYS, series, water_today

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.get("/series")
async def get_series(
    metric_key: str,
    zone_id: str | None = None,
    minutes: int = Query(60, ge=1, le=7 * 24 * 60),
    points: int = Query(60, ge=2, le=500),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Bucket-averaged history for charts."""
    if metric_key not in METRIC_KEYS:
        raise HTTPException(422, f"metric_key must be one of {list(METRIC_KEYS)}")
    if metric_key.startswith("zone.") and not zone_id:
        raise HTTPException(422, "zone metrics need zone_id")
    return {
        "metric_key": metric_key,
        "zone_id": zone_id,
        "minutes": minutes,
        "points": await series(db, metric_key, zone_id, minutes, points),
    }


@router.get("/water-today")
async def get_water_today(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """Water delivered per zone since farm-local midnight, in m³."""
    zones = await water_today(db)
    return {"zones": zones, "total_m3": round(sum(z["m3"] for z in zones), 3)}
