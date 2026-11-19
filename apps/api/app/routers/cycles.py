"""Irrigation cycle endpoints — /api/v1/cycles (Milestone D)."""

import math
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor
from app.models.irrigation_cycle import IrrigationCycle
from app.schemas.cycle import CyclesPageResponse, IrrigationCycleResponse

router = APIRouter(prefix="/cycles", tags=["Cycles"])


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
    query = select(IrrigationCycle)

    if zone_id:
        query = query.where(IrrigationCycle.zone_id == zone_id)
    if outcome:
        query = query.where(IrrigationCycle.outcome == outcome)
    if program_id:
        query = query.where(IrrigationCycle.program_id == program_id)
    if from_date:
        query = query.where(IrrigationCycle.actual_start_at >= from_date)
    if to_date:
        query = query.where(IrrigationCycle.actual_start_at <= to_date)

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
    items = [IrrigationCycleResponse.model_validate(c) for c in cycles]
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
        .where(IrrigationCycle.zone_id == zone_id)
        .order_by(desc(IrrigationCycle.actual_start_at))
        .limit(limit)
    )
    return [IrrigationCycleResponse.model_validate(c) for c in res.scalars().all()]
