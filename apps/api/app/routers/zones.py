"""Zone endpoints — CRUD /api/v1/zones."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneResponse, ZoneUpdate

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get("", response_model=list[ZoneResponse])
async def list_zones(db: AsyncSession = Depends(get_db)):
    """List all zones."""
    result = await db.execute(select(Zone).order_by(Zone.priority))
    return result.scalars().all()


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    """Get zone by ID."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    return zone


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    update: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update zone configuration."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    await db.flush()
    await db.refresh(zone)
    return zone
