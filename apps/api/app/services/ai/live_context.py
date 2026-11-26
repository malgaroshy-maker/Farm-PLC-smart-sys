"""Compact live snapshot for AI prompts (Milestone G2).

Most operator questions ("how full is the tank?", "do I need to irrigate today?") are
answered by this block alone, so the model rarely needs tool round-trips — each one is
a full extra LLM request. Only real values are included; anything missing is said so.
"""

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.services.alarms import active_alarm_responses
from app.services.live_state import build_map_state, is_fresh, load_snapshots
from app.services.weather import is_usable_forecast, weather_service

log = logging.getLogger(__name__)

ARABIC_STYLE = """
Arabic writing rules (whenever you write Arabic):
- Modern Standard Arabic only. No English words inside Arabic sentences; units and codes such as ET₀, m³, ALM-012 are allowed.
- Use Western digits 0-9 (never ٠١٢٣٤٥٦٧٨٩).
- Terms: evapotranspiration = التبخر-نتح; reference evapotranspiration = التبخر-نتح المرجعي ET₀; drip irrigation = الري بالتنقيط;
  valve = صمام; booster pump = مضخة التعزيز; well pump = مضخة البئر; water tank = الخزان; soil moisture = رطوبة التربة;
  flow = التدفق; pressure = الضغط; irrigation zone = منطقة ري; pomegranate = رمان; mother pomegranates = رمان أمهات;
  olive = زيتون; grapes = عنب; irrigation cycle = دورة ري; alarm = إنذار.
- Units: م³ (m³), مم (mm), bar, °C, %.
"""

SNAPSHOT_RULE = (
    "Answer directly from the LIVE FARM SNAPSHOT below. Call tools only for details it does not contain "
    "(cycle history, a specific alarm's details, telemetry trends). Label simulated readings when reporting them."
)


def _f(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


async def build_live_snapshot_block(
    factory: async_sessionmaker[AsyncSession] | None = None, *, facts: dict | None = None
) -> str:
    factory = factory or async_session_factory
    lines: list[str] = []
    facts = {} if facts is None else facts
    try:
        async with factory() as db:
            snapshots = await load_snapshots(db)
            state = build_map_state(snapshots, await active_alarm_responses(db))
            stats = snapshots.get("simulation_stats")
            readings = stats.state if stats else {}
            fresh = bool(stats and is_fresh({"simulation_stats": stats}))
            facts["tank_pct"] = readings.get("tank_level_pct")
            facts["fresh"] = fresh
            simulated = settings.deployment_mode == "simulation"
            facts["simulated"] = simulated
            tz = ZoneInfo(settings.farm_timezone)
            now_local = clock.farm_now().astimezone(tz)
            lines.append(
                f"LIVE FARM SNAPSHOT (farm time {now_local:%Y-%m-%d %H:%M} Africa/Tripoli; "
                f"source {'simulation' if simulated else 'controller'}, "
                f"live data {'fresh' if fresh else 'unavailable or stale - quote only last known readings'})"
            )
            lines.append(
                f"- Tank {_f(readings.get('tank_level_pct'))} %, main flow {_f(readings.get('main_flow_m3h'), 2)} m³/h, "
                f"main pressure {_f(readings.get('main_pressure_bar'), 2)} bar, "
                f"mode {state.system_mode if 'system_mode' in snapshots else 'unavailable'}"
            )
            pumps = ", ".join(
                f"{p.pump_id}={p.state}{' FAULT' if p.fault else ''}" for p in state.pumps
            )
            lines.append(f"- Pumps: {pumps or 'none reported'}")
            running = [z for z in state.zones if z.state == "running"]
            if running:
                lines.append(
                    "- Irrigating now: "
                    + "; ".join(
                        f"{z.zone_id} (moisture {_f(z.moisture_pct)} %, flow {_f(z.flow_m3h, 2)} m³/h, "
                        f"{int(z.runtime_sec // 60)} min)"
                        for z in running
                    )
                )
            else:
                lines.append(
                    "- Irrigating now: none reported"
                    if state.zones
                    else "- Irrigation state unavailable"
                )
            with_m = [z for z in state.zones if z.moisture_pct is not None]
            if with_m:
                dry = sorted(with_m, key=lambda z: z.moisture_pct)[:4]
                avg = sum(z.moisture_pct for z in with_m) / len(with_m)
                facts["moisture_avg"] = avg
                facts["driest"] = [(z.zone_id, z.moisture_pct) for z in dry]
                lines.append(
                    f"- Soil moisture: farm average {avg:.0f} %; driest "
                    + ", ".join(f"{z.zone_id} {z.moisture_pct:.0f} %" for z in dry)
                )
            alarms = state.active_alarms or []
            facts["alarm_count"] = len(alarms)
            facts["running"] = [z.zone_id for z in running]
            if alarms:
                items = []
                for a in alarms[:6]:
                    get = a.get if isinstance(a, dict) else (lambda k, _a=a: getattr(_a, k, None))
                    items.append(
                        f"{get('alarm_code')} {get('severity')} {get('name') or ''} ({get('zone_id') or 'system'})"
                    )
                lines.append(f"- Active alarms ({len(alarms)}): " + "; ".join(items))
            else:
                lines.append("- Active alarms in the app: none recorded")
            try:
                from app.routers.schedules import get_upcoming_runs

                runs = await get_upcoming_runs(hours=24, _=None, db=db)
                if runs:
                    r = runs[0]
                    facts["next_run"] = {
                        "time": r.scheduled_start_farm[11:16],
                        "zone_ar": r.zone_name_ar or r.zone_name,
                        "zone_en": r.zone_name,
                        "minutes": r.duration_min,
                    }
                    lines.append(
                        f"- Next irrigation: program '{r.program_name}' at {r.scheduled_start_farm} (farm time), "
                        f"zone {r.zone_id} ({r.zone_name}), {r.duration_min} min, "
                        f"in {int(r.seconds_until_start // 3600)} h {int(r.seconds_until_start % 3600 // 60)} min"
                    )
                else:
                    facts["next_run"] = None
                    lines.append("- Next irrigation: none in the next 24 h")
            except Exception as exc:  # pragma: no cover - schedule shape changes must not break AI
                log.debug("snapshot: upcoming runs unavailable: %s", exc)
    except Exception as exc:
        log.warning("Could not build live snapshot: %s", exc)
        lines.append("LIVE FARM SNAPSHOT: unavailable")

    fc = weather_service._cached_forecast  # cached only: never block the answer on the network
    today = clock.farm_now().astimezone(ZoneInfo(settings.farm_timezone)).date()
    daily = {d.date: d for d in fc.daily} if fc and is_usable_forecast(fc) else {}
    for label, day in (("today", today), ("tomorrow", today + timedelta(days=1))):
        d = daily.get(day.isoformat())
        if d is not None:
            lines.append(
                f"- Weather {label}: max {_f(d.temp_max_c, 0)}°C min {_f(d.temp_min_c, 0)}°C, "
                f"rain {_f(d.precipitation_total_mm)} mm ({_f(d.precipitation_probability_pct, 0)} %), "
                f"ET₀ {_f(d.et0_mm, 2)} mm"
            )
    d0 = daily.get(today.isoformat())
    if d0 is not None:
        facts["weather"] = {
            "max": d0.temp_max_c,
            "rain_mm": d0.precipitation_total_mm,
            "rain_pct": d0.precipitation_probability_pct,
            "et0": d0.et0_mm,
        }
    else:
        lines.append("- Weather today: forecast unavailable (say so if asked)")
    return "\n".join(lines)
