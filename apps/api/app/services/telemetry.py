"""
Telemetry history: samples live state into telemetry_points every
`telemetry_interval_sec` and serves bucket-averaged series for charts.

Metric keys
  system:  tank_level_pct, main_pressure_bar, main_flow_m3h
  zone:    zone.moisture_pct, zone.flow_m3h, zone.pressure_bar   (zone_id set)
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.models.telemetry import TelemetryPoint
from app.services.live_state import Snapshot

SYSTEM_METRICS = ("tank_level_pct", "main_pressure_bar", "main_flow_m3h")
ZONE_METRICS = ("moisture_pct", "flow_m3h", "pressure_bar")
METRIC_KEYS = (*SYSTEM_METRICS, *(f"zone.{m}" for m in ZONE_METRICS))


class Recorder:
    def __init__(self) -> None:
        self._last_farm: datetime | None = None
        self._last_real: datetime | None = None

    @property
    def _last(self) -> datetime | None:
        return self._last_farm

    @_last.setter
    def _last(self, val: datetime | None) -> None:
        self._last_farm = val
        self._last_real = val

    async def maybe_record(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> int:
        now_real = utcnow()
        now_farm = clock.farm_now()
        # Telemetry every 10 s farm time, at most 1/s real (bypassed in tests where interval == 0)
        if settings.telemetry_interval_sec > 0:
            if self._last_real and (now_real - self._last_real).total_seconds() < 1.0:
                return 0
            if (
                self._last_farm
                and (now_farm - self._last_farm).total_seconds() < settings.telemetry_interval_sec
            ):
                return 0
        self._last_real = now_real
        self._last_farm = now_farm
        points: list[TelemetryPoint] = []

        def add(metric: str, value, zone_id: str | None = None) -> None:
            if isinstance(value, int | float):
                points.append(
                    TelemetryPoint(
                        metric_key=metric,
                        farm_id=settings.farm_id,
                        zone_id=zone_id,
                        ts=now_farm,
                        value_numeric=float(value),
                        value_text=str(clock.speed),
                        source="simulator" if settings.deployment_mode == "simulation" else "plc",
                    )
                )

        stats = snapshots.get("simulation_stats")
        if stats:
            for m in SYSTEM_METRICS:
                add(m, stats.state.get(m))
        for key, snap in snapshots.items():
            if key.startswith("zone_"):
                zid = snap.state.get("zone_id")
                for m in ZONE_METRICS:
                    add(f"zone.{m}", snap.state.get(m), zid)
        db.add_all(points)
        await db.commit()
        return len(points)


async def series(
    db: AsyncSession, metric_key: str, zone_id: str | None, minutes: int, points: int
) -> list[dict]:
    """Bucket-averaged series, oldest first: [{ts, value, min, max}]."""
    end = clock.farm_now()
    start = end - timedelta(minutes=minutes)
    q = select(TelemetryPoint.ts, TelemetryPoint.value_numeric).where(
        TelemetryPoint.metric_key == metric_key, TelemetryPoint.ts >= start
    )
    q = (
        q.where(TelemetryPoint.zone_id == zone_id)
        if zone_id
        else q.where(TelemetryPoint.zone_id.is_(None))
    )
    rows = (await db.execute(q.order_by(TelemetryPoint.ts))).all()

    bucket_s = max(1.0, minutes * 60 / max(1, points))
    buckets: dict[int, list[float]] = {}
    for ts, value in rows:
        if value is None:
            continue
        idx = int((as_utc(ts) - start).total_seconds() // bucket_s)
        buckets.setdefault(idx, []).append(value)
    return [
        {
            "ts": (start + timedelta(seconds=(i + 0.5) * bucket_s)).isoformat(),
            "value": round(sum(v) / len(v), 3),
            "min": round(min(v), 3),
            "max": round(max(v), 3),
        }
        for i, v in sorted(buckets.items())
    ]


MAX_GAP_S = 60.0  # default/base gap limit at 1x speed


def max_gap_s(speed: float) -> float:
    """Maximum allowed gap in farm seconds between consecutive samples.

    Farm-time sample spacing is max(10 s, speed * 1 s).
    Allows ~3× the expected spacing: max(60.0, 3.0 * max(10.0, speed * 1.0)).
    At 1×: 60 s (so a 10-minute outage is rejected).
    At 360×: 1080 s (~18 farm minutes, so normal 360 s spacing is accepted).
    """
    return max(60.0, 3.0 * max(10.0, speed * 1.0))


def farm_midnight_utc(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(settings.farm_timezone)
    local = (now or clock.farm_now()).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def water_today(db: AsyncSession) -> list[dict]:
    """m³ delivered per zone since farm-local midnight.

    Primary source: irrigation_cycles (closed runs + live integration for running cycle).
    Fallback: direct telemetry trapezoidal integration if no cycles exist.
    """
    from app.models.irrigation_cycle import IrrigationCycle

    since = farm_midnight_utc()
    now_farm = clock.farm_now()

    # 1. Closed cycles today
    cycles_res = await db.execute(
        select(IrrigationCycle.zone_id, IrrigationCycle.water_estimate_m3).where(
            IrrigationCycle.actual_end_at >= since,
            IrrigationCycle.water_estimate_m3.is_not(None),
        )
    )
    cycle_rows = cycles_res.all()
    totals: dict[str, float] = {}
    has_cycles = False
    for zid, m3 in cycle_rows:
        has_cycles = True
        totals[zid] = totals.get(zid, 0.0) + (m3 or 0.0)

    # 2. Open cycles in progress
    open_res = await db.execute(
        select(IrrigationCycle.zone_id, IrrigationCycle.actual_start_at).where(
            IrrigationCycle.actual_end_at.is_(None),
            IrrigationCycle.actual_start_at >= since,
        )
    )
    for zid, start_at in open_res.all():
        has_cycles = True
        # Integrate live flow for running cycle
        run_rows = (
            await db.execute(
                select(TelemetryPoint.ts, TelemetryPoint.value_numeric, TelemetryPoint.value_text)
                .where(
                    TelemetryPoint.metric_key == "zone.flow_m3h",
                    TelemetryPoint.zone_id == zid,
                    TelemetryPoint.ts >= start_at,
                    TelemetryPoint.ts <= now_farm,
                )
                .order_by(TelemetryPoint.ts)
            )
        ).all()
        live_m3 = 0.0
        prev_p = None
        for ts, v, val_text in run_rows:
            ts = as_utc(ts)
            v = v or 0.0
            try:
                s_speed = float(val_text) if val_text else 1.0
            except (ValueError, TypeError):
                s_speed = 1.0
            if prev_p:
                pts, pv, p_speed = prev_p
                dt = (ts - pts).total_seconds()
                limit = max_gap_s(max(s_speed, p_speed))
                if 0 < dt <= limit:
                    live_m3 += (pv + v) / 2 * dt / 3600.0
            prev_p = (ts, v, s_speed)
        totals[zid] = totals.get(zid, 0.0) + live_m3

    if has_cycles:
        return [{"zone_id": z, "m3": round(m3, 3)} for z, m3 in sorted(totals.items())]

    # Fallback to pure telemetry trapezoid integration
    rows = (
        await db.execute(
            select(
                TelemetryPoint.zone_id,
                TelemetryPoint.ts,
                TelemetryPoint.value_numeric,
                TelemetryPoint.value_text,
            )
            .where(TelemetryPoint.metric_key == "zone.flow_m3h", TelemetryPoint.ts >= since)
            .order_by(TelemetryPoint.zone_id, TelemetryPoint.ts)
        )
    ).all()
    prev: dict[str, tuple[datetime, float, float]] = {}
    for zone_id, ts, value, val_text in rows:
        ts = as_utc(ts)
        v = value or 0.0
        try:
            s_speed = float(val_text) if val_text else 1.0
        except (ValueError, TypeError):
            s_speed = 1.0
        if zone_id in prev:
            pts, pv, p_speed = prev[zone_id]
            dt = (ts - pts).total_seconds()
            effective_speed = max(s_speed, p_speed)
            limit = max_gap_s(effective_speed)
            if 0 < dt <= limit:
                totals[zone_id] = totals.get(zone_id, 0.0) + (pv + v) / 2 * dt / 3600.0
        totals.setdefault(zone_id, 0.0)
        prev[zone_id] = (ts, v, s_speed)
    return [{"zone_id": z, "m3": round(m3, 3)} for z, m3 in sorted(totals.items())]


async def prune_old(db: AsyncSession) -> None:
    cutoff = clock.farm_now() - timedelta(days=settings.telemetry_retention_days)
    await db.execute(delete(TelemetryPoint).where(TelemetryPoint.ts < cutoff))
    await db.commit()


recorder = Recorder()
