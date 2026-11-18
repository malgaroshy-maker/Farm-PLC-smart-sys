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
from app.core.timeutil import as_utc, utcnow
from app.models.telemetry import TelemetryPoint
from app.services.live_state import Snapshot

SYSTEM_METRICS = ("tank_level_pct", "main_pressure_bar", "main_flow_m3h")
ZONE_METRICS = ("moisture_pct", "flow_m3h", "pressure_bar")
METRIC_KEYS = (*SYSTEM_METRICS, *(f"zone.{m}" for m in ZONE_METRICS))


class Recorder:
    def __init__(self) -> None:
        self._last: datetime | None = None

    async def maybe_record(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> int:
        now = utcnow()
        if self._last and (now - self._last).total_seconds() < settings.telemetry_interval_sec:
            return 0
        self._last = now
        points: list[TelemetryPoint] = []

        def add(metric: str, value, zone_id: str | None = None) -> None:
            if isinstance(value, int | float):
                points.append(
                    TelemetryPoint(
                        metric_key=metric,
                        farm_id=settings.farm_id,
                        zone_id=zone_id,
                        ts=now,
                        value_numeric=float(value),
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
    end = utcnow()
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


MAX_GAP_S = 60.0  # don't integrate across data gaps (comms loss, simulator off)


def farm_midnight_utc(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(settings.farm_timezone)
    local = (now or utcnow()).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def water_today(db: AsyncSession) -> list[dict]:
    """m³ delivered per zone since farm-local midnight (trapezoid over zone.flow_m3h)."""
    since = farm_midnight_utc()
    rows = (
        await db.execute(
            select(TelemetryPoint.zone_id, TelemetryPoint.ts, TelemetryPoint.value_numeric)
            .where(TelemetryPoint.metric_key == "zone.flow_m3h", TelemetryPoint.ts >= since)
            .order_by(TelemetryPoint.zone_id, TelemetryPoint.ts)
        )
    ).all()
    totals: dict[str, float] = {}
    prev: dict[str, tuple[datetime, float]] = {}
    for zone_id, ts, value in rows:
        ts = as_utc(ts)
        v = value or 0.0
        if zone_id in prev:
            pts, pv = prev[zone_id]
            dt = (ts - pts).total_seconds()
            if 0 < dt <= MAX_GAP_S:
                totals[zone_id] = totals.get(zone_id, 0.0) + (pv + v) / 2 * dt / 3600.0
        totals.setdefault(zone_id, 0.0)
        prev[zone_id] = (ts, v)
    return [{"zone_id": z, "m3": round(m3, 3)} for z, m3 in sorted(totals.items())]


async def prune_old(db: AsyncSession) -> None:
    cutoff = utcnow() - timedelta(days=settings.telemetry_retention_days)
    await db.execute(delete(TelemetryPoint).where(TelemetryPoint.ts < cutoff))
    await db.commit()


recorder = Recorder()
