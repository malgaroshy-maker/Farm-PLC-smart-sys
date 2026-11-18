"""Zone endpoints — CRUD /api/v1/zones."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_admin, require_roles
from app.models.zone import Zone
from app.schemas.zone import ZoneResponse, ZoneUpdate
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


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str,
    update: ZoneUpdate,
    _: Actor = Depends(require_admin),
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
