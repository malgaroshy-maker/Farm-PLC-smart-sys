"""Irrigation cycle endpoints — /api/v1/cycles (Milestone D)."""

import math
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import as_utc
from app.database import get_db
from app.deps import Actor, get_actor
from app.models.irrigation_cycle import IrrigationCycle
from app.schemas.cycle import CyclesPageResponse, IrrigationCycleResponse
from app.services.telemetry import known_cycle_water

router = APIRouter(prefix="/cycles", tags=["Cycles"])


def _as_response(cycle: IrrigationCycle) -> IrrigationCycleResponse:
    item = IrrigationCycleResponse.model_validate(cycle)
    item.water_estimate_m3 = known_cycle_water(item.water_estimate_m3, item.water_is_estimate)
    if item.water_estimate_m3 is None and item.actual_end_at is not None:
        item.water_is_estimate = False
        item.water_has_gaps = True
    return item


@router.get("", response_model=CyclesPageResponse)
async def list_cycles(
    zone_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    program_id: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """List irrigation cycles with pagination and filters."""
    query = select(IrrigationCycle).where(
        ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True)
    )

    if zone_id:
        query = query.where(IrrigationCycle.zone_id == zone_id)
    if outcome:
        query = query.where(IrrigationCycle.outcome == outcome)
    if program_id:
        query = query.where(IrrigationCycle.program_id == program_id)
    if from_date:
        query = query.where(IrrigationCycle.actual_start_at >= as_utc(from_date))
    if to_date:
        query = query.where(IrrigationCycle.actual_start_at <= as_utc(to_date))

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paged query
    query = (
        query.order_by(desc(IrrigationCycle.actual_start_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    cycles = result.scalars().all()

    pages = max(1, math.ceil(total / page_size))
    items = [_as_response(c) for c in cycles]
    return CyclesPageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/recent/{zone_id}", response_model=list[IrrigationCycleResponse])
async def get_recent_zone_cycles(
    zone_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Recent irrigation cycles for a specific zone (for ZoneDrawer history)."""
    res = await db.execute(
        select(IrrigationCycle)
        .where(
            IrrigationCycle.zone_id == zone_id,
            ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
        )
        .order_by(desc(IrrigationCycle.actual_start_at))
        .limit(limit)
    )
    return [_as_response(c) for c in res.scalars().all()]
