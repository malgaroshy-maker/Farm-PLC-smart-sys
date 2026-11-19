"""Read-Only Live Context Tools for AI Agent (Milestone E).

Strictly read-only — no write or command tools.
Provides live farm context:
  1. get_alarm(alarm_id)
  2. get_zone_state(zone_id)
  3. get_recent_telemetry(hours)
  4. get_cycles(days)
  5. get_schedule()
  6. get_forecast()
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydantic_ai import RunContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import clock
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.services.live_state import load_snapshots
from app.services.weather import weather_service


@dataclass
class AIDeps:
    """Dependencies passed to the Pydantic AI Agent."""

    db: AsyncSession | None = None


async def get_alarm(ctx: RunContext[AIDeps], alarm_id: str) -> dict[str, Any]:
    """Retrieve details and diagnostic guidance for an active or past alarm."""

    async def _query(db: AsyncSession) -> dict[str, Any]:
        stmt = (
            select(Alarm)
            .where((Alarm.id == alarm_id) | (Alarm.alarm_code == alarm_id))
            .order_by(desc(Alarm.triggered_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        alarm = res.scalar_one_or_none()
        if not alarm:
            return {"error": f"Alarm '{alarm_id}' not found"}

        return {
            "id": alarm.id,
            "alarm_code": alarm.alarm_code,
            "name": alarm.name,
            "name_ar": alarm.name_ar,
            "severity": alarm.severity,
            "category": alarm.category,
            "status": alarm.status,
            "zone_id": alarm.zone_id,
            "device_id": alarm.device_id,
            "current_value": alarm.current_value,
            "threshold_value": alarm.threshold_value,
            "triggered_at": alarm.triggered_at.isoformat(),
            "message_en": alarm.message_en,
            "message_ar": alarm.message_ar,
            "guidance_en": alarm.guidance_en,
            "guidance_ar": alarm.guidance_ar,
            "condition_active": alarm.condition_active,
        }

    if ctx.deps.db is not None:
        return await _query(ctx.deps.db)
    async with async_session_factory() as db:
        return await _query(db)


async def get_zone_state(ctx: RunContext[AIDeps], zone_id: str) -> dict[str, Any]:
    """Retrieve current physical and operational state for an irrigation zone."""

    async def _query(db: AsyncSession) -> dict[str, Any]:
        zone = await db.get(Zone, zone_id)
        if not zone:
            return {"error": f"Zone '{zone_id}' not found"}

        snapshots = await load_snapshots(db)
        snap = snapshots.get(f"zone:{zone.id}")
        live_data = snap.data if snap else {}

        return {
            "zone_id": zone.id,
            "zone_code": zone.zone_code,
            "name": zone.name,
            "crop_type": zone.crop_type,
            "area_ha": zone.area_ha,
            "target_flow_m3h": zone.target_flow_m3h,
            "min_pressure_bar": zone.min_pressure_bar,
            "max_pressure_bar": zone.max_pressure_bar,
            "enabled": zone.enabled,
            "state": live_data.get("state", "idle"),
            "flow_m3h": live_data.get("flow_m3h", 0.0),
            "pressure_bar": live_data.get("pressure_bar", 0.0),
            "valve_open": live_data.get("valve_state") == "open",
        }

    if ctx.deps.db is not None:
        return await _query(ctx.deps.db)
    async with async_session_factory() as db:
        return await _query(db)


async def get_recent_telemetry(ctx: RunContext[AIDeps], hours: int = 1) -> dict[str, Any]:
    """Retrieve summary of recent hydraulic telemetry (flow and pressure metrics)."""

    async def _query(db: AsyncSession) -> dict[str, Any]:
        hours_capped = max(1, min(hours, 24))
        cutoff = clock.farm_now() - timedelta(hours=hours_capped)

        stmt = (
            select(TelemetryPoint)
            .where(TelemetryPoint.ts >= cutoff)
            .order_by(desc(TelemetryPoint.ts))
            .limit(500)
        )
        res = await db.execute(stmt)
        points = list(res.scalars().all())

        if not points:
            return {
                "window_hours": hours_capped,
                "data_points": 0,
                "message": "No telemetry recorded in this time window",
            }

        flows = [
            p.value_numeric
            for p in points
            if "flow" in p.metric_key and p.value_numeric is not None
        ]
        pressures = [
            p.value_numeric
            for p in points
            if "pressure" in p.metric_key and p.value_numeric is not None
        ]

        return {
            "window_hours": hours_capped,
            "data_points": len(points),
            "avg_flow_m3h": round(sum(flows) / len(flows), 2) if flows else 0.0,
            "max_flow_m3h": round(max(flows), 2) if flows else 0.0,
            "avg_pressure_bar": round(sum(pressures) / len(pressures), 2) if pressures else 0.0,
            "min_pressure_bar": round(min(pressures), 2) if pressures else 0.0,
            "max_pressure_bar": round(max(pressures), 2) if pressures else 0.0,
            "latest_flow_m3h": round(flows[0], 2) if flows else 0.0,
            "latest_pressure_bar": round(pressures[0], 2) if pressures else 0.0,
        }

    if ctx.deps.db is not None:
        return await _query(ctx.deps.db)
    async with async_session_factory() as db:
        return await _query(db)


async def get_cycles(ctx: RunContext[AIDeps], days: int = 1) -> list[dict[str, Any]]:
    """Retrieve irrigation cycle history for the past N days."""

    async def _query(db: AsyncSession) -> list[dict[str, Any]]:
        days_capped = max(1, min(days, 14))
        cutoff = clock.farm_now() - timedelta(days=days_capped)

        stmt = (
            select(IrrigationCycle)
            .where(
                (IrrigationCycle.actual_start_at >= cutoff) | (IrrigationCycle.created_at >= cutoff)
            )
            .order_by(desc(IrrigationCycle.created_at))
            .limit(100)
        )
        res = await db.execute(stmt)
        cycles = list(res.scalars().all())

        return [
            {
                "cycle_id": c.id,
                "zone_id": c.zone_id,
                "program_id": c.program_id,
                "outcome": c.outcome,
                "started_at": (c.actual_start_at or c.created_at).isoformat(),
                "duration_min": float(c.actual_duration_min or 0.0),
                "water_volume_m3": float(c.water_estimate_m3 or 0.0),
                "failure_reason": c.failure_reason,
            }
            for c in cycles
        ]

    if ctx.deps.db is not None:
        return await _query(ctx.deps.db)
    async with async_session_factory() as db:
        return await _query(db)


async def get_schedule(ctx: RunContext[AIDeps]) -> list[dict[str, Any]]:
    """Retrieve configured irrigation schedules and sequential program steps."""

    async def _query(db: AsyncSession) -> list[dict[str, Any]]:
        stmt = select(Program).where(Program.enabled.is_(True)).options(selectinload(Program.steps))
        res = await db.execute(stmt)
        programs = list(res.scalars().all())

        return [
            {
                "program_id": p.id,
                "name": p.name,
                "start_time_local": p.start_time_local,
                "weekday_mask": p.weekday_mask,
                "season": p.season,
                "steps": [
                    {
                        "step_order": s.step_order,
                        "zone_id": s.zone_id,
                        "duration_min": s.duration_min,
                    }
                    for s in p.steps
                ],
            }
            for p in programs
        ]

    if ctx.deps.db is not None:
        return await _query(ctx.deps.db)
    async with async_session_factory() as db:
        return await _query(db)


async def get_forecast(ctx: RunContext[AIDeps]) -> dict[str, Any]:
    """Retrieve weather forecast, precipitation risk, and evapotranspiration (ET0)."""
    forecast = await weather_service.get_forecast(db=ctx.deps.db)
    today = forecast.daily[0] if forecast.daily else None

    return {
        "current_temperature_c": forecast.current.temperature_c,
        "current_humidity_pct": forecast.current.humidity_pct,
        "current_condition": forecast.current.condition,
        "current_description": forecast.current.description,
        "today_max_temp_c": today.temp_max_c if today else 30.0,
        "today_min_temp_c": today.temp_min_c if today else 18.0,
        "today_precipitation_mm": today.precipitation_total_mm if today else 0.0,
        "today_precipitation_prob_pct": today.precipitation_probability_pct if today else 0.0,
        "today_et0_mm": today.et0_mm if today else 4.5,
        "days": [
            {
                "date": d.date,
                "temp_max_c": d.temp_max_c,
                "precip_mm": d.precipitation_total_mm,
                "precip_prob_pct": d.precipitation_probability_pct,
                "et0_mm": d.et0_mm,
                "condition": d.condition,
            }
            for d in forecast.daily[:3]
        ],
    }


AI_TOOLS = [
    get_alarm,
    get_zone_state,
    get_recent_telemetry,
    get_cycles,
    get_schedule,
    get_forecast,
]
