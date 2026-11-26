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
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic_ai import RunContext
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program
from app.models.schedule import Schedule
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.services.ai.redaction import redact_payload, redact_text
from app.services.live_state import is_fresh, load_snapshots
from app.services.telemetry import known_cycle_water
from app.services.weather import is_usable_forecast, weather_service

log = logging.getLogger(__name__)


@dataclass
class AIDeps:
    """Dependencies passed to the Pydantic AI Agent."""

    session_factory: async_sessionmaker[AsyncSession] = async_session_factory


async def _resolve_zone_id(db: AsyncSession, reference: str) -> str | None:
    value = reference.strip().lower()
    canonical = await db.scalar(select(Zone.id).where(func.lower(Zone.id) == value))
    if canonical:
        return canonical
    matches = list(
        (
            await db.scalars(
                select(Zone.id)
                .where(
                    (func.lower(Zone.code) == value)
                    | (func.lower(Zone.name) == value)
                    | (Zone.name_ar == reference.strip())
                )
                .limit(2)
            )
        ).all()
    )
    return matches[0] if len(matches) == 1 else None


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
                return {"error": "Alarm not found"}

            from app.core.alarm_catalog import CATALOG

            spec = CATALOG.get(alarm.alarm_code)
            return redact_payload(
                {
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
                    "message_en": spec.message_en if spec else None,
                    "message_ar": spec.message_ar if spec else None,
                    "guidance_en": spec.guidance_en if spec else None,
                    "guidance_ar": spec.guidance_ar if spec else None,
                    "condition_active": alarm.status in ("active_unacked", "active_acked"),
                }
            )
    except Exception as exc:
        log.warning("get_alarm tool error: %s", type(exc).__name__)
        return {"error": "Alarm details are unavailable"}


async def get_zone_state(ctx: RunContext[AIDeps], zone_id: str) -> dict[str, Any]:
    """Retrieve current physical and operational state for an irrigation zone."""
    try:
        factory = (
            ctx.deps.session_factory
            if ctx and ctx.deps and ctx.deps.session_factory
            else async_session_factory
        )
        async with factory() as db:
            canonical = await _resolve_zone_id(db, zone_id)
            zone = await db.get(Zone, canonical) if canonical else None
            if not zone:
                return {"error": "Unknown or ambiguous zone. Use its configured code or ID."}

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
                "name": redact_text(zname),
                "name_ar": redact_text(zname_ar) if zname_ar else None,
                "crop_type": zcrop,
                "area_ha": zarea,
                "min_pressure_bar": zp_min,
                "max_pressure_bar": zp_max,
                "min_flow_m3h": zf_min,
                "max_flow_m3h": zf_max,
                "enabled": zenabled,
                "state": live_data.get("state"),
                "flow_m3h": live_data.get("flow_m3h"),
                "pressure_bar": live_data.get("pressure_bar"),
                "valve_open": (
                    live_data["valve_state"] == "open" if "valve_state" in live_data else None
                ),
                "updated_at": snap.updated_at.isoformat() if snap else None,
                "data_fresh": is_fresh({zid: snap}) if snap else False,
            }
    except Exception as exc:
        log.warning("get_zone_state tool error: %s", type(exc).__name__)
        return {"error": "Zone state is unavailable"}


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
                select(TelemetryPoint.metric_key, TelemetryPoint.value_numeric, TelemetryPoint.ts)
                .where(TelemetryPoint.ts >= cutoff)
                .order_by(desc(TelemetryPoint.ts))
                .limit(501)
            )
            if zone_id:
                canonical = await _resolve_zone_id(db, zone_id)
                if canonical is None:
                    return {"error": "Unknown or ambiguous zone. Use its configured code or ID."}
                stmt = stmt.where(TelemetryPoint.zone_id == canonical)
            res = await db.execute(stmt)
            points = res.all()

            if not points:
                return {
                    "window_hours": hours_capped,
                    "data_points": 0,
                    "message": "No telemetry recorded in this time window",
                }

            samples = points[:500]
            flows = [val for key, val, _ in samples if "flow" in key and val is not None]
            pressures = [val for key, val, _ in samples if "pressure" in key and val is not None]

            return {
                "window_hours": hours_capped,
                "data_points": len(samples),
                "truncated": len(points) > 500,
                "latest_sample_at": samples[0].ts.isoformat(),
                "avg_flow_m3h": round(sum(flows) / len(flows), 2) if flows else None,
                "max_flow_m3h": round(max(flows), 2) if flows else None,
                "avg_pressure_bar": round(sum(pressures) / len(pressures), 2)
                if pressures
                else None,
                "min_pressure_bar": round(min(pressures), 2) if pressures else None,
                "max_pressure_bar": round(max(pressures), 2) if pressures else None,
                "latest_flow_m3h": round(flows[0], 2) if flows else None,
                "latest_pressure_bar": round(pressures[0], 2) if pressures else None,
            }
    except Exception as exc:
        log.warning("get_recent_telemetry tool error: %s", type(exc).__name__)
        return {"error": "Recent telemetry is unavailable"}


async def get_cycles(
    ctx: RunContext[AIDeps],
    days: int = 1,
    zone_id: str | None = None,
    local_date: str | None = None,
) -> dict[str, Any]:
    """Read cycle history for a rolling window or an exact farm-local YYYY-MM-DD date."""
    factory = ctx.deps.session_factory if ctx and ctx.deps else async_session_factory
    return await read_cycles(factory, days=days, zone_id=zone_id, local_date=local_date)


async def read_cycles(
    factory: async_sessionmaker[AsyncSession],
    *,
    days: int = 1,
    zone_id: str | None = None,
    local_date: str | None = None,
) -> dict[str, Any]:
    try:
        async with factory() as db:
            days_capped = max(1, min(days, 14))
            now = clock.farm_now()
            cutoff, end = now - timedelta(days=days_capped), now
            if local_date:
                try:
                    day = date.fromisoformat(local_date)
                except ValueError:
                    return {"error": "Use a YYYY-MM-DD local date"}
                tz = ZoneInfo(settings.farm_timezone)
                cutoff = datetime.combine(day, time.min, tzinfo=tz).astimezone(now.tzinfo)
                end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(
                    now.tzinfo
                )

            started = func.coalesce(IrrigationCycle.actual_start_at, IrrigationCycle.created_at)

            stmt = (
                select(IrrigationCycle)
                .where(
                    started >= cutoff,
                    started < end,
                    ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
                )
                .order_by(desc(started))
                .limit(101)
            )
            if zone_id:
                canonical = await _resolve_zone_id(db, zone_id)
                if canonical is None:
                    return {"error": "Unknown or ambiguous zone. Use its configured code or ID."}
                stmt = stmt.where(IrrigationCycle.zone_id == canonical)
            res = await db.execute(stmt)
            cycles = list(res.scalars().all())

            records = []
            for c in cycles[:100]:
                volume = known_cycle_water(c.water_estimate_m3, c.water_is_estimate)
                records.append(
                    {
                        "cycle_id": c.id,
                        "zone_id": c.zone_id,
                        "program_id": c.program_id,
                        "outcome": c.outcome,
                        "started_at": (c.actual_start_at or c.created_at).isoformat(),
                        "duration_min": c.actual_duration_min,
                        "water_volume_m3": volume,
                        "water_is_estimate": c.water_is_estimate if volume is not None else None,
                        "water_has_gaps": c.water_has_gaps or volume is None,
                        "failure_reason": redact_text(c.failure_reason)
                        if c.failure_reason
                        else None,
                    }
                )
            return {
                "local_date": local_date,
                "deployment_mode": settings.deployment_mode,
                "from": cutoff.isoformat(),
                "to": end.isoformat(),
                "truncated": len(cycles) > 100,
                "cycles": records,
            }
    except Exception as exc:
        log.warning("get_cycles tool error: %s", type(exc).__name__)
        return {"error": "Cycle history is unavailable"}


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
                canonical = await _resolve_zone_id(db, zone_id)
                if canonical is None:
                    return {"error": "Unknown or ambiguous zone. Use its configured code or ID."}
                programs = [p for p in programs if any(s.zone_id == canonical for s in p.steps)]
                schedules = [s for s in schedules if s.zone_id == canonical]

            return {
                "programs": [
                    {
                        "program_id": p.id,
                        "name": redact_text(p.name),
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
        log.warning("get_schedule tool error: %s", type(exc).__name__)
        return {"error": "Schedules are unavailable"}


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
        if not forecast or not is_usable_forecast(forecast):
            return {"available": False, "source": forecast.source if forecast else None, "days": []}
        today_date = (
            clock.farm_now().astimezone(ZoneInfo(settings.farm_timezone)).date().isoformat()
        )
        today = next((day for day in forecast.daily if day.date == today_date), None)

        return {
            "available": True,
            "source": forecast.source,
            "last_fetched_at": forecast.last_fetched_at,
            "cached": forecast.cached,
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
        log.warning("get_forecast tool error: %s", type(exc).__name__)
        return {"error": "Forecast is unavailable"}


AI_TOOLS = [
    get_alarm,
    get_zone_state,
    get_recent_telemetry,
    get_cycles,
    get_schedule,
    get_forecast,
]
