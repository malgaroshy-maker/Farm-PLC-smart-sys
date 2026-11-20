"""Read-Only Live Context Tools for AI Agent (Milestone E).

Strictly read-only — no write or command tools.
Provides live farm context:
  1. get_alarm(alarm_id)
  2. get_zone_state(zone_id)
  3. get_recent_telemetry(hours)
  4. get_cycles(days)
  5. get_schedule()
  6. get_forecast()

Concurrency-safe: AIDeps holds an async_sessionmaker factory.
Each tool acquires its own session so parallel tool calls execute cleanly.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydantic_ai import RunContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.clock import clock
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program
from app.models.schedule import Schedule
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.services.live_state import load_snapshots
from app.services.weather import weather_service

log = logging.getLogger(__name__)


@dataclass
class AIDeps:
    """Dependencies passed to the Pydantic AI Agent."""

    session_factory: async_sessionmaker[AsyncSession] = async_session_factory


async def get_alarm(ctx: RunContext[AIDeps], alarm_id: str) -> dict[str, Any]:
    """Retrieve details and diagnostic guidance for an active or past alarm."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
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

            from app.core.alarm_catalog import CATALOG

            spec = CATALOG.get(alarm.alarm_code)
            return {
                "id": alarm.id,
                "alarm_code": alarm.alarm_code,
                "name": spec.name if spec else alarm.alarm_code,
                "name_ar": spec.name_ar if spec else alarm.alarm_code,
                "severity": alarm.severity,
                "category": alarm.category,
                "status": alarm.status,
                "zone_id": alarm.zone_id,
                "device_id": alarm.device_id,
                "current_value": alarm.current_value,
                "threshold_value": alarm.threshold_value,
                "triggered_at": alarm.triggered_at.isoformat() if alarm.triggered_at else None,
                "message_en": alarm.message_en,
                "message_ar": alarm.message_ar,
                "guidance_en": alarm.guidance_en,
                "guidance_ar": alarm.guidance_ar,
                "condition_active": alarm.status in ("active_unacked", "active_acked"),
            }
    except Exception as exc:
        log.warning("get_alarm tool error: %s", exc)
        return {"error": f"Failed to get alarm '{alarm_id}': {exc}"}


async def get_zone_state(ctx: RunContext[AIDeps], zone_id: str) -> dict[str, Any]:
    """Retrieve current physical and operational state for an irrigation zone."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            zone = await db.get(Zone, zone_id)
            if not zone:
                stmt = select(Zone).where((Zone.id == zone_id) | (Zone.code == zone_id))
                res = await db.execute(stmt)
                zone = res.scalar_one_or_none()
            if not zone:
                return {"error": f"Zone '{zone_id}' not found"}

            zid = zone.id
            zcode = zone.code
            zname = zone.name
            zname_ar = zone.name_ar
            zcrop = zone.crop_type
            zarea = zone.area_ha
            zp_min = getattr(zone, "pressure_min_bar", 1.5)
            zp_max = getattr(zone, "pressure_max_bar", 4.0)
            zf_min = getattr(zone, "flow_min_m3h", 2.0)
            zf_max = getattr(zone, "flow_max_m3h", 10.0)
            zenabled = zone.enabled

            snapshots = await load_snapshots(db)
            snap = snapshots.get(f"zone_{zid}") or snapshots.get(f"zone:{zid}")
            live_data = (
                snap.state
                if snap and hasattr(snap, "state")
                else (snap.data if snap and hasattr(snap, "data") else {})
            )

            return {
                "zone_id": zid,
                "code": zcode,
                "name": zname,
                "name_ar": zname_ar,
                "crop_type": zcrop,
                "area_ha": zarea,
                "min_pressure_bar": zp_min,
                "max_pressure_bar": zp_max,
                "min_flow_m3h": zf_min,
                "max_flow_m3h": zf_max,
                "enabled": zenabled,
                "state": live_data.get("state", "idle"),
                "flow_m3h": live_data.get("flow_m3h", 0.0),
                "pressure_bar": live_data.get("pressure_bar", 0.0),
                "valve_open": live_data.get("valve_state") == "open",
            }
    except Exception as exc:
        log.warning("get_zone_state tool error: %s", exc)
        return {"error": f"Failed to get zone state '{zone_id}': {exc}"}


async def get_recent_telemetry(
    ctx: RunContext[AIDeps], hours: int = 1, zone_id: str | None = None
) -> dict[str, Any]:
    """Recent hydraulic telemetry (flow and pressure). Optionally for one zone_id."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            hours_capped = max(1, min(hours, 24))
            cutoff = clock.farm_now() - timedelta(hours=hours_capped)

            stmt = (
                select(TelemetryPoint.metric_key, TelemetryPoint.value_numeric)
                .where(TelemetryPoint.ts >= cutoff)
                .order_by(desc(TelemetryPoint.ts))
                .limit(500)
            )
            if zone_id:
                stmt = stmt.where(TelemetryPoint.zone_id == zone_id)
            res = await db.execute(stmt)
            points = res.all()

            if not points:
                return {
                    "window_hours": hours_capped,
                    "data_points": 0,
                    "message": "No telemetry recorded in this time window",
                }

            flows = [val for key, val in points if "flow" in key and val is not None]
            pressures = [val for key, val in points if "pressure" in key and val is not None]

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
    except Exception as exc:
        log.warning("get_recent_telemetry tool error: %s", exc, exc_info=True)
        return {"error": f"Failed to get recent telemetry: {exc}"}


async def get_cycles(
    ctx: RunContext[AIDeps], days: int = 1, zone_id: str | None = None
) -> list[dict[str, Any]]:
    """Irrigation cycle history for the past N days. Optionally for one zone_id."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            days_capped = max(1, min(days, 14))
            cutoff = clock.farm_now() - timedelta(days=days_capped)

            stmt = (
                select(IrrigationCycle)
                .where(
                    (IrrigationCycle.actual_start_at >= cutoff)
                    | (IrrigationCycle.created_at >= cutoff)
                )
                .order_by(desc(IrrigationCycle.created_at))
                .limit(100)
            )
            if zone_id:
                stmt = stmt.where(IrrigationCycle.zone_id == zone_id)
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
    except Exception as exc:
        log.warning("get_cycles tool error: %s", exc)
        return [{"error": f"Failed to get cycles: {exc}"}]


async def get_schedule(ctx: RunContext[AIDeps], zone_id: str | None = None) -> dict[str, Any]:
    """Configured irrigation programs and schedules. Optionally only those including zone_id."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            # Multi-zone sequential programs
            p_stmt = (
                select(Program)
                .where(Program.enabled.is_(True))
                .options(selectinload(Program.steps))
            )
            p_res = await db.execute(p_stmt)
            programs = list(p_res.scalars().all())

            # Individual zone schedules
            s_stmt = select(Schedule).where(Schedule.enabled.is_(True))
            s_res = await db.execute(s_stmt)
            schedules = list(s_res.scalars().all())
            if zone_id:
                programs = [p for p in programs if any(s.zone_id == zone_id for s in p.steps)]
                schedules = [s for s in schedules if s.zone_id == zone_id]

            return {
                "programs": [
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
                ],
                "schedules": [
                    {
                        "schedule_id": s.id,
                        "zone_id": s.zone_id,
                        "start_time_local": s.start_time_local,
                        "duration_min": s.duration_min,
                        "recurrence_rule": s.recurrence_rule,
                        "weekday_mask": s.weekday_mask,
                    }
                    for s in schedules
                ],
            }
    except Exception as exc:
        log.warning("get_schedule tool error: %s", exc)
        return {"error": f"Failed to get schedules: {exc}", "programs": [], "schedules": []}


async def get_forecast(ctx: RunContext[AIDeps], days: int = 3) -> dict[str, Any]:
    """Farm weather forecast: rain probability/amount, temperature, ET0 (up to 7 days)."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            forecast = await weather_service.get_forecast(db=db)
        today = forecast.daily[0] if forecast.daily else None

        return {
            "current_temperature_c": forecast.current.temperature_c,
            "current_humidity_pct": forecast.current.humidity_pct,
            "current_condition": forecast.current.condition,
            "current_description": forecast.current.description,
            # No invented values: None when the forecast has no daily data.
            "today_max_temp_c": today.temp_max_c if today else None,
            "today_min_temp_c": today.temp_min_c if today else None,
            "today_precipitation_mm": today.precipitation_total_mm if today else None,
            "today_precipitation_prob_pct": today.precipitation_probability_pct if today else None,
            "today_et0_mm": today.et0_mm if today else None,
            "days": [
                {
                    "date": d.date,
                    "temp_max_c": d.temp_max_c,
                    "precip_mm": d.precipitation_total_mm,
                    "precip_prob_pct": d.precipitation_probability_pct,
                    "et0_mm": d.et0_mm,
                    "condition": d.condition,
                }
                for d in forecast.daily[: max(1, min(days, 7))]
            ],
        }
    except Exception as exc:
        log.warning("get_forecast tool error: %s", exc)
        return {"error": f"Failed to get forecast: {exc}"}


AI_TOOLS = [
    get_alarm,
    get_zone_state,
    get_recent_telemetry,
    get_cycles,
    get_schedule,
    get_forecast,
]
