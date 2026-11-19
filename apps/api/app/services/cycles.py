"""Irrigation cycle logger — records all runs (manual, scheduled, scenario) (Milestone D).

Integrates water volume (m³) from zone.flow_m3h telemetry with speed-aware gap limit,
links alarm codes raised during the run, and determines cycle outcome.
"""

import json
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import clock
from app.core.timeutil import as_utc
from app.deps import Actor
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.services.telemetry import max_gap_s

log = logging.getLogger(__name__)


async def integrate_zone_water_m3(
    db: AsyncSession, zone_id: str, start_time: datetime, end_time: datetime
) -> tuple[float, bool]:
    """Trapezoidal integration of zone.flow_m3h telemetry points between start and end time.

    Returns (water_m3, is_estimate):
    - With >= 2 real samples: calculates trapezoidal integration; is_estimate = False.
    - With < 2 samples: estimates water from available sample or nominal flow × duration; is_estimate = True.
    """
    start_utc = as_utc(start_time)
    end_utc = as_utc(end_time)
    if end_utc <= start_utc:
        return 0.0, False

    res = await db.execute(
        select(TelemetryPoint.ts, TelemetryPoint.value_numeric, TelemetryPoint.value_text)
        .where(
            TelemetryPoint.metric_key == "zone.flow_m3h",
            TelemetryPoint.zone_id == zone_id,
            TelemetryPoint.ts >= start_utc,
            TelemetryPoint.ts <= end_utc,
        )
        .order_by(TelemetryPoint.ts)
    )
    rows = res.all()

    # If 2 or more samples exist, compute trapezoidal integration
    if len(rows) >= 2:
        total_m3 = 0.0
        prev_ts: datetime | None = None
        prev_val = 0.0
        prev_speed = 1.0

        for ts, val, val_text in rows:
            ts = as_utc(ts)
            v = val or 0.0
            try:
                speed = float(val_text) if val_text else 1.0
            except (ValueError, TypeError):
                speed = 1.0

            if prev_ts is not None:
                dt = (ts - prev_ts).total_seconds()
                effective_speed = max(speed, prev_speed)
                gap_limit = max_gap_s(effective_speed)
                if 0 < dt <= gap_limit:
                    total_m3 += (prev_val + v) / 2.0 * dt / 3600.0

            prev_ts = ts
            prev_val = v
            prev_speed = speed

        # Measured: a run with zero flow (e.g. valve never opened) used no water.
        return round(total_m3, 4), False

    # Fewer than 2 samples: extrapolate the single measured flow, flagged as an
    # estimate. Never invent water from the zone's nominal flow.
    dt_hours = max(0.0, (end_utc - start_utc).total_seconds() / 3600.0)
    if rows and dt_hours > 0:
        return round((rows[0][1] or 0.0) * dt_hours, 4), True
    # No samples at all: unknown, recorded as 0 and flagged so the UI shows ≈.
    return 0.0, dt_hours > 0


async def get_linked_alarms_json(
    db: AsyncSession, zone_id: str, start_time: datetime, end_time: datetime
) -> str | None:
    """Find alarms triggered for this zone during the cycle run."""
    start_utc = as_utc(start_time)
    end_utc = as_utc(end_time)

    res = await db.execute(
        select(Alarm.alarm_code).where(
            Alarm.zone_id == zone_id,
            Alarm.triggered_at >= start_utc,
            Alarm.triggered_at <= end_utc,
        )
    )
    codes = sorted(set(res.scalars().all()))
    return json.dumps(codes) if codes else None


async def record_cycle_start(
    db: AsyncSession,
    cmd: Command,
    zone: Zone,
    actor: Actor,
    payload: dict | None = None,
) -> IrrigationCycle:
    """Create an open irrigation_cycles row when a start_zone command is accepted."""
    now = clock.farm_now()
    pl = payload or {}
    prog_id = pl.get("program_id")
    step_id = pl.get("program_step_id")
    duration = pl.get("duration_min") or zone.max_runtime_min
    src_mode = pl.get("source_mode") or "tank"

    cycle = IrrigationCycle(
        id=f"cyc_{uuid4().hex[:12]}",
        zone_id=zone.id,
        source_mode=src_mode,
        program_id=prog_id,
        program_step_id=step_id,
        command_id=cmd.id,
        planned_start_at=now,
        actual_start_at=now,
        actual_end_at=None,
        planned_duration_min=duration,
        actual_duration_min=None,
        outcome=None,  # in progress
        water_estimate_m3=None,
        water_is_estimate=False,
        initiated_by_type=actor.actor_type,
        initiated_by_id=actor.actor_id,
        alarms_json=None,
        failure_reason=None,
        notes=pl.get("notes"),
        created_at=now,
        updated_at=now,
    )
    db.add(cycle)
    await db.flush()
    return cycle


async def record_cycle_end_for_zone(
    db: AsyncSession,
    zone_id: str,
    outcome: str | None = None,
    failure_reason: str | None = None,
) -> IrrigationCycle | None:
    """Close the active open cycle for a zone when the zone returns to idle/off."""
    res = await db.execute(
        select(IrrigationCycle)
        .where(
            IrrigationCycle.zone_id == zone_id,
            IrrigationCycle.actual_end_at.is_(None),
        )
        .order_by(desc(IrrigationCycle.actual_start_at))
    )
    cycle = res.scalars().first()
    if not cycle:
        return None

    now = as_utc(clock.farm_now())
    start_at = as_utc(cycle.actual_start_at) if cycle.actual_start_at else now
    end_at = max(now, start_at)

    cycle.actual_end_at = end_at
    duration_min = max(0, int((end_at - start_at).total_seconds() // 60))
    cycle.actual_duration_min = duration_min

    # Calculate water used and flag whether estimated
    water_m3, is_estimate = await integrate_zone_water_m3(db, zone_id, start_at, end_at)
    cycle.water_estimate_m3 = water_m3
    cycle.water_is_estimate = is_estimate

    # Link alarm codes
    alarms = await get_linked_alarms_json(db, zone_id, start_at, end_at)
    cycle.alarms_json = alarms

    # Determine outcome
    if outcome:
        cycle.outcome = outcome
    elif alarms:
        cycle.outcome = "faulted"
    elif cycle.planned_duration_min and duration_min >= (cycle.planned_duration_min - 1):
        cycle.outcome = "completed"
    else:
        cycle.outcome = "manual_stop"

    if failure_reason:
        cycle.failure_reason = failure_reason
    cycle.updated_at = now

    await db.flush()
    return cycle


async def record_cycle_aborted_by_command(
    db: AsyncSession,
    command_id: str,
    failure_reason: str | None = None,
) -> IrrigationCycle | None:
    """Close the active cycle linked to a command when that command enters a terminal failure state.

    Ensures that if a start fails, times out, or is superseded before the zone moves,
    the cycle is marked aborted with failure_reason exactly once.
    """
    res = await db.execute(
        select(IrrigationCycle).where(
            IrrigationCycle.command_id == command_id,
            IrrigationCycle.actual_end_at.is_(None),
        )
    )
    cycle = res.scalars().first()
    if not cycle:
        return None

    now = as_utc(clock.farm_now())
    start_at = as_utc(cycle.actual_start_at) if cycle.actual_start_at else now
    end_at = max(now, start_at)

    cycle.actual_end_at = end_at
    cycle.actual_duration_min = max(0, int((end_at - start_at).total_seconds() // 60))
    cycle.outcome = "aborted"
    cycle.failure_reason = failure_reason or "Command terminated before zone started"
    cycle.water_estimate_m3 = 0.0
    cycle.water_is_estimate = False
    cycle.updated_at = now
    await db.flush()
    return cycle


async def record_cycles_aborted_on_jump(
    db: AsyncSession, jump_time: datetime
) -> list[IrrigationCycle]:
    """Abort all open runs when a farm clock jump occurs."""
    res = await db.execute(select(IrrigationCycle).where(IrrigationCycle.actual_end_at.is_(None)))
    open_cycles = list(res.scalars().all())
    jump_utc = as_utc(jump_time)
    for cycle in open_cycles:
        start_at = as_utc(cycle.actual_start_at) if cycle.actual_start_at else jump_utc
        end_at = max(jump_utc, start_at)
        cycle.actual_end_at = end_at
        cycle.actual_duration_min = max(0, int((end_at - start_at).total_seconds() // 60))
        water_m3, is_estimate = await integrate_zone_water_m3(db, cycle.zone_id, start_at, end_at)
        cycle.water_estimate_m3 = water_m3
        cycle.water_is_estimate = is_estimate
        cycle.outcome = "aborted"
        cycle.failure_reason = "clock jump"
        cycle.updated_at = jump_utc
    await db.flush()
    return open_cycles


async def record_cycle_skipped(
    db: AsyncSession,
    program_id: str,
    program_step_id: str,
    zone_id: str,
    planned_duration_min: int,
    reason: str,
) -> IrrigationCycle:
    """Record a skipped cycle when a scheduled step is refused by an interlock."""
    now = clock.farm_now()
    cycle = IrrigationCycle(
        id=f"cyc_{uuid4().hex[:12]}",
        zone_id=zone_id,
        source_mode="tank",
        program_id=program_id,
        program_step_id=program_step_id,
        planned_start_at=now,
        actual_start_at=now,
        actual_end_at=now,
        planned_duration_min=planned_duration_min,
        actual_duration_min=0,
        outcome="skipped",
        water_estimate_m3=0.0,
        water_is_estimate=False,
        initiated_by_type="scheduler",
        failure_reason=reason,
        notes=f"Skipped by scheduler: {reason}",
        created_at=now,
        updated_at=now,
    )
    db.add(cycle)
    await db.flush()
    return cycle
