"""Schedule and program endpoints — /api/v1/schedules (Milestone D)."""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.database import get_db
from app.deps import Actor, get_actor, require_admin, require_roles
from app.models.program import Program, ProgramStep
from app.models.zone import Zone
from app.schemas.schedule import (
    ConflictCheckRequest,
    ProgramCreate,
    ProgramResponse,
    ProgramStepSchema,
    ProgramToggle,
    ProgramUpdate,
    UpcomingRun,
)
from app.services.conflicts import check_program_conflicts, parse_weekday_mask

router = APIRouter(prefix="/schedules", tags=["Schedules"])
require_operator_or_admin = require_roles("owner_admin", "operator")


def _to_program_response(p: Program) -> ProgramResponse:
    steps = [
        ProgramStepSchema(
            id=s.id,
            program_id=s.program_id,
            zone_id=s.zone_id,
            step_order=s.step_order,
            duration_min=s.duration_min,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in p.steps
    ]
    total_min = sum(s.duration_min for s in p.steps)
    return ProgramResponse(
        id=p.id,
        name=p.name,
        enabled=p.enabled,
        start_time_local=p.start_time_local,
        weekday_mask=p.weekday_mask,
        season=p.season,
        notes=p.notes,
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
        steps=steps,
        total_duration_min=total_min,
    )


async def _get_zones_map(db: AsyncSession) -> dict[str, Zone]:
    res = await db.execute(select(Zone))
    return {z.id: z for z in res.scalars().all()}


async def _get_all_programs(db: AsyncSession) -> list[Program]:
    res = await db.execute(
        select(Program).options(selectinload(Program.steps)).order_by(Program.created_at)
    )
    return list(res.scalars().all())


async def _get_program(db: AsyncSession, program_id: str) -> Program | None:
    res = await db.execute(
        select(Program).options(selectinload(Program.steps)).where(Program.id == program_id)
    )
    return res.scalar_one_or_none()


@router.get("", response_model=list[ProgramResponse])
async def list_programs(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """List all irrigation programs with their steps and total duration."""
    programs = await _get_all_programs(db)
    return [_to_program_response(p) for p in programs]


@router.get("/upcoming", response_model=list[UpcomingRun])
async def get_upcoming_runs(
    hours: int = Query(default=24, ge=1, le=168),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Next irrigation runs in farm time for dashboard and mobile status cards."""
    programs = await _get_all_programs(db)
    zones = await _get_zones_map(db)

    now_farm = clock.farm_now()
    farm_tz = ZoneInfo(settings.farm_timezone)
    now_local = now_farm.astimezone(farm_tz)
    end_local = now_local + timedelta(hours=hours)

    upcoming: list[UpcomingRun] = []

    # Check dates covering the lookahead window
    curr_date = (now_local - timedelta(days=1)).date()
    end_date = (end_local + timedelta(days=1)).date()

    while curr_date <= end_date:
        weekday = curr_date.isoweekday()  # 1=Monday ... 7=Sunday
        for p in programs:
            if not p.enabled or not p.steps:
                continue
            active_days = parse_weekday_mask(p.weekday_mask)
            if weekday not in active_days:
                continue

            try:
                h, m = map(int, p.start_time_local.split(":"))
                prog_start_dt = datetime(
                    curr_date.year,
                    curr_date.month,
                    curr_date.day,
                    h,
                    m,
                    tzinfo=farm_tz,
                )
            except Exception:
                continue

            step_start = prog_start_dt
            for step in p.steps:
                step_end = step_start + timedelta(minutes=step.duration_min)
                # If step starts within the window and has not already finished
                if step_end > now_local and step_start <= end_local:
                    zone = zones.get(step.zone_id)
                    zname = zone.name if zone else step.zone_id
                    zname_ar = zone.name_ar if zone else None
                    crop = zone.crop_type if zone else None

                    sec_until = max(0.0, (step_start - now_local).total_seconds())
                    upcoming.append(
                        UpcomingRun(
                            program_id=p.id,
                            program_name=p.name,
                            step_order=step.step_order,
                            zone_id=step.zone_id,
                            zone_name=zname,
                            zone_name_ar=zname_ar,
                            crop_type=crop,
                            scheduled_start_farm=step_start.isoformat(),
                            duration_min=step.duration_min,
                            seconds_until_start=sec_until,
                        )
                    )
                step_start = step_end

        curr_date += timedelta(days=1)

    upcoming.sort(key=lambda u: (u.seconds_until_start, u.step_order))
    return upcoming


@router.post("/check-conflicts")
async def check_conflicts(
    req: ConflictCheckRequest,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Live conflict check for the program editor (G6: the editor called this but it was
    missing). Same rules as create/update; the first conflict is returned for display."""
    conflicts = check_program_conflicts(
        candidate_name=req.program.name,
        candidate_start_time=req.program.start_time_local,
        candidate_weekday_mask=req.program.weekday_mask,
        candidate_steps=[s.model_dump() for s in req.program.steps],
        existing_programs=await _get_all_programs(db),
        zones_by_id=await _get_zones_map(db),
        candidate_id=req.exclude_program_id,
    )
    return {
        "ok": not conflicts,
        "conflict": conflicts[0].to_dict() if conflicts else None,
        "conflicts": [c.to_dict() for c in conflicts],
    }


@router.post("", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    req: ProgramCreate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new irrigation program (Admin only). Validates with conflict checker."""
    zones = await _get_zones_map(db)
    existing = await _get_all_programs(db)

    steps_data = [s.model_dump() for s in req.steps]
    conflicts = check_program_conflicts(
        candidate_name=req.name,
        candidate_start_time=req.start_time_local,
        candidate_weekday_mask=req.weekday_mask,
        candidate_steps=steps_data,
        existing_programs=existing,
        zones_by_id=zones,
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "CONFLICT",
                "conflicts": [c.to_dict() for c in conflicts],
            },
        )

    now = clock.farm_now()
    program_id = f"prog_{uuid4().hex[:12]}"
    program = Program(
        id=program_id,
        name=req.name,
        enabled=req.enabled,
        start_time_local=req.start_time_local,
        weekday_mask=req.weekday_mask,
        season=req.season,
        notes=req.notes,
        created_by=actor.actor_id,
        created_at=now,
        updated_at=now,
    )
    db.add(program)

    for idx, s in enumerate(req.steps, start=1):
        step_id = f"step_{uuid4().hex[:12]}"
        step = ProgramStep(
            id=step_id,
            program_id=program_id,
            zone_id=s.zone_id,
            step_order=idx,
            duration_min=s.duration_min,
            created_at=now,
            updated_at=now,
        )
        db.add(step)

    await db.commit()
    # Reload with relationships
    created = await _get_program(db, program_id)
    return _to_program_response(created)


@router.get("/{program_id}", response_model=ProgramResponse)
async def get_program(
    program_id: str,
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Get single program by ID."""
    p = await _get_program(db, program_id)
    if not p:
        raise HTTPException(status_code=404, detail="Program not found")
    return _to_program_response(p)


@router.patch("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: str,
    req: ProgramUpdate,
    _: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update program configuration (Admin only). Validates with conflict checker."""
    program = await _get_program(db, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    zones = await _get_zones_map(db)
    existing = await _get_all_programs(db)

    name = req.name if req.name is not None else program.name
    start_time = (
        req.start_time_local if req.start_time_local is not None else program.start_time_local
    )
    mask = req.weekday_mask if req.weekday_mask is not None else program.weekday_mask

    if req.steps is not None:
        steps_data = [s.model_dump() for s in req.steps]
    else:
        steps_data = [
            {"zone_id": s.zone_id, "duration_min": s.duration_min, "step_order": s.step_order}
            for s in program.steps
        ]

    # Only run overlap conflict check if program is enabled or being enabled
    is_enabled = req.enabled if req.enabled is not None else program.enabled
    if is_enabled:
        conflicts = check_program_conflicts(
            candidate_name=name,
            candidate_start_time=start_time,
            candidate_weekday_mask=mask,
            candidate_steps=steps_data,
            existing_programs=existing,
            zones_by_id=zones,
            candidate_id=program_id,
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CONFLICT",
                    "conflicts": [c.to_dict() for c in conflicts],
                },
            )

    now = clock.farm_now()
    if req.name is not None:
        program.name = req.name
    if req.enabled is not None:
        program.enabled = req.enabled
    if req.start_time_local is not None:
        program.start_time_local = req.start_time_local
    if req.weekday_mask is not None:
        program.weekday_mask = req.weekday_mask
    if req.season is not None:
        program.season = req.season
    if req.notes is not None:
        program.notes = req.notes
    program.updated_at = now

    if req.steps is not None:
        # Replace steps
        program.steps.clear()
        for idx, s in enumerate(req.steps, start=1):
            step_id = f"step_{uuid4().hex[:12]}"
            st = ProgramStep(
                id=step_id,
                program_id=program_id,
                zone_id=s.zone_id,
                step_order=idx,
                duration_min=s.duration_min,
                created_at=now,
                updated_at=now,
            )
            program.steps.append(st)

    await db.commit()
    updated = await _get_program(db, program_id)
    return _to_program_response(updated)


@router.patch("/{program_id}/toggle", response_model=ProgramResponse)
async def toggle_program(
    program_id: str,
    req: ProgramToggle,
    _: Actor = Depends(require_operator_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an irrigation program (Operator+)."""
    program = await _get_program(db, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    if req.enabled and not program.enabled:
        # Check conflicts before enabling
        zones = await _get_zones_map(db)
        existing = await _get_all_programs(db)
        steps_data = [
            {"zone_id": s.zone_id, "duration_min": s.duration_min, "step_order": s.step_order}
            for s in program.steps
        ]
        conflicts = check_program_conflicts(
            candidate_name=program.name,
            candidate_start_time=program.start_time_local,
            candidate_weekday_mask=program.weekday_mask,
            candidate_steps=steps_data,
            existing_programs=existing,
            zones_by_id=zones,
            candidate_id=program_id,
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CONFLICT",
                    "conflicts": [c.to_dict() for c in conflicts],
                },
            )

    program.enabled = req.enabled
    program.updated_at = clock.farm_now()
    await db.commit()
    return _to_program_response(program)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    program_id: str,
    _: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an irrigation program (Admin only)."""
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    await db.delete(program)
    await db.commit()
