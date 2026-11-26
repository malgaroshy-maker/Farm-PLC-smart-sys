"""
Telemetry history: samples live state into telemetry_points every
`telemetry_interval_sec` and serves bucket-averaged series for charts.

Metric keys
  system:  tank_level_pct, main_pressure_bar, main_flow_m3h
  zone:    zone.moisture_pct, zone.flow_m3h, zone.pressure_bar   (zone_id set)
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.services.live_state import Snapshot, is_fresh

SYSTEM_METRICS = (
    "tank_level_pct",
    "main_pressure_bar",
    "main_flow_m3h",
    "well_level_m",
    "filter_dp_bar",
)
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
            if isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value):
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
        if stats and is_fresh({"simulation_stats": stats}, now_real):
            for m in SYSTEM_METRICS:
                add(m, stats.state.get(m))
        for key, snap in snapshots.items():
            if (
                not 0
                <= (now_real - as_utc(snap.updated_at)).total_seconds()
                <= settings.state_stale_after_sec
            ):
                continue
            if key.startswith("zone_"):
                zid = snap.state.get("zone_id")
                for m in ZONE_METRICS:
                    add(f"zone.{m}", snap.state.get(m), zid)
            elif key.startswith("pump_"):  # G7 pump health
                pid = snap.state.get("pump_id")
                add(f"pump.{pid}.power_kw", snap.state.get("power_kw"))
        db.add_all(points)
        await db.commit()
        return len(points)


async def series(
    db: AsyncSession,
    metric_key: str,
    zone_id: str | None,
    minutes: int,
    points: int,
    *,
    end: datetime | None = None,
) -> list[dict]:
    """Bucket-averaged series, oldest first: [{ts, value, min, max}].

    The averaging happens in the database (GROUP BY time bucket), so a 60-point chart
    reads ~60 rows instead of every raw sample (Milestone G1).
    """
    end = end or clock.farm_now()
    start = end - timedelta(minutes=minutes)
    bucket_s = max(1.0, minutes * 60 / max(1, points))
    sqlite = db.bind.dialect.name == "sqlite"
    if sqlite:
        bucket = "CAST((julianday(ts) - julianday(:start)) * 86400.0 / :bucket AS INTEGER)"
        start_param = as_utc(start).replace(tzinfo=None).isoformat(sep=" ")
        end_param = as_utc(end).replace(tzinfo=None).isoformat(sep=" ")
    else:  # PostgreSQL
        bucket = "CAST(FLOOR(EXTRACT(EPOCH FROM (ts - :start)) / :bucket) AS INTEGER)"
        start_param = start
        end_param = end
    zone_sql = "zone_id = :zone_id" if zone_id else "zone_id IS NULL"
    rows = (
        await db.execute(
            text(
                f"""
                SELECT {bucket} AS b, AVG(value_numeric), MIN(value_numeric), MAX(value_numeric)
                FROM telemetry_points
                WHERE metric_key = :metric AND {zone_sql} AND ts >= :start_cmp
                  AND ts <= :end_cmp AND value_numeric IS NOT NULL
                GROUP BY b
                ORDER BY b
                """
            ),
            {
                "start": start_param,
                "start_cmp": start_param,
                "end_cmp": end_param,
                "bucket": bucket_s,
                "metric": metric_key,
                "zone_id": zone_id,
            },
        )
    ).all()
    return [
        {
            "ts": (start + timedelta(seconds=(int(b) + 0.5) * bucket_s)).isoformat(),
            "value": round(avg, 3),
            "min": round(lo, 3),
            "max": round(hi, 3),
        }
        for b, avg, lo, hi in rows
        if b is not None and 0 <= b < points + 1
    ]


async def flow_pressure_series(db: AsyncSession) -> list[dict]:
    end = clock.farm_now()
    flow = await series(db, "main_flow_m3h", None, 60, 60, end=end)
    pressure = await series(db, "main_pressure_bar", None, 60, 60, end=end)
    flow_by_time = {point["ts"]: point["value"] for point in flow}
    pressure_by_time = {point["ts"]: point["value"] for point in pressure}
    observed = flow_by_time.keys() | pressure_by_time.keys()
    if not observed:
        return []
    first = datetime.fromisoformat(min(observed))
    last = datetime.fromisoformat(max(observed))
    points = []
    for minute in range(int((last - first).total_seconds() // 60) + 1):
        ts = (first + timedelta(minutes=minute)).isoformat()
        points.append(
            {"ts": ts, "flow": flow_by_time.get(ts), "pressure": pressure_by_time.get(ts)}
        )
    return points


MAX_GAP_S = 60.0  # default/base gap limit at 1x speed


def max_gap_s(speed: float) -> float:
    """Maximum allowed gap in farm seconds between consecutive samples.

    Farm-time sample spacing is max(10 s, speed * 1 s).
    Allows ~3× the expected spacing: max(60.0, 3.0 * max(10.0, speed * 1.0)).
    At 1×: 60 s (so a 10-minute outage is rejected).
    At 360×: 1080 s (~18 farm minutes, so normal 360 s spacing is accepted).
    """
    return max(60.0, 3.0 * max(10.0, speed * 1.0))


FlowSample = tuple[datetime, float | None, str | None, str]
_GENERATED_BASELINE_OFFSETS = (30, 300, 600, 900, 1200, 1500)


@dataclass
class FlowVolume:
    m3: float | None = None
    covered_seconds: float = 0.0
    first_rate: float | None = None
    rate_count: int = 0
    covered_from: datetime | None = None
    covered_to: datetime | None = None
    edge_allowance_s: float = 0.0

    def has_gaps(self, start: datetime, stop: datetime) -> bool:
        """True when readings are missing from start..stop.

        Readings never fall exactly on a run's first and last second, so each end may be
        short by one normal sampling interval. A break in the middle always counts.
        """
        if self.covered_from is None or self.covered_to is None:
            return True
        span = (self.covered_to - self.covered_from).total_seconds()
        return (
            span - self.covered_seconds > 0.001
            or (self.covered_from - start).total_seconds() > self.edge_allowance_s
            or (stop - self.covered_to).total_seconds() > self.edge_allowance_s
        )


def integrate_flow(samples: Iterable[FlowSample], start: datetime, stop: datetime) -> FlowVolume:
    """Integrate confirmed intervals, clipping a pair at midnight or a cycle boundary."""
    total = FlowVolume()
    previous: tuple[datetime, float, float] | None = None
    for timestamp, rate, speed_text, quality in samples:
        timestamp = as_utc(timestamp)
        if quality != "good" or rate is None or not isfinite(rate) or rate < 0:
            previous = None
            continue
        try:
            speed = float(speed_text or "1")
        except (ValueError, TypeError):
            speed = 1.0
        speed = speed if isfinite(speed) and speed >= 0 else 1.0
        if start <= timestamp <= stop:
            total.rate_count += 1
            if total.first_rate is None:
                total.first_rate = rate

        if previous:
            prior_time, prior_rate, prior_speed = previous
            duration = (timestamp - prior_time).total_seconds()
            left, right = max(start, prior_time), min(stop, timestamp)
            if left < right and 0 < duration <= max_gap_s(max(speed, prior_speed)):
                seconds = (right - left).total_seconds()
                slope = (rate - prior_rate) / duration
                left_rate = prior_rate + slope * (left - prior_time).total_seconds()
                right_rate = prior_rate + slope * (right - prior_time).total_seconds()
                total.m3 = (total.m3 or 0) + (left_rate + right_rate) * seconds / 7200
                total.covered_seconds += seconds
                total.covered_from = total.covered_from or left
                total.covered_to = right
                # samples are 10 farm seconds apart, or one per real second when faster
                interval = max(10.0, speed, prior_speed)
                total.edge_allowance_s = max(total.edge_allowance_s, 1.5 * interval)
        previous = (timestamp, rate, speed)
    return total


def known_cycle_water(value: float | None, estimated: bool) -> float | None:
    # Older cycle rows used estimated zero as a placeholder when no flow was recorded.
    if value is None or not isfinite(value) or value < 0 or (estimated and value == 0):
        return None
    return value


async def generated_flow_timestamps(
    db: AsyncSession, start: datetime, stop: datetime, zone_id: str | None = None
) -> set[tuple[str, datetime]]:
    """Locate samples inserted by the retired anomaly demo alongside its baseline cycles."""
    query = select(IrrigationCycle.zone_id, IrrigationCycle.actual_start_at).where(
        IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
        IrrigationCycle.actual_start_at <= stop,
        IrrigationCycle.actual_end_at >= start,
    )
    if zone_id is not None:
        query = query.where(IrrigationCycle.zone_id == zone_id)
    return {
        (zone, as_utc(begin) + timedelta(seconds=offset))
        for zone, begin in await db.execute(query)
        for offset in _GENERATED_BASELINE_OFFSETS
    }


def farm_midnight_utc(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(settings.farm_timezone)
    local = (now or clock.farm_now()).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def water_today(db: AsyncSession) -> list[dict]:
    """Summarize evidence for each zone between farm-local midnight and the farm clock."""
    now_farm = as_utc(clock.farm_now())
    since = farm_midnight_utc(now_farm)
    cycles = (
        await db.execute(
            select(
                IrrigationCycle.zone_id,
                IrrigationCycle.actual_start_at,
                IrrigationCycle.actual_end_at,
                IrrigationCycle.water_estimate_m3,
                IrrigationCycle.water_is_estimate,
                IrrigationCycle.water_has_gaps,
            ).where(
                IrrigationCycle.actual_start_at <= now_farm,
                or_(IrrigationCycle.actual_end_at.is_(None), IrrigationCycle.actual_end_at > since),
                ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
            )
        )
    ).all()
    totals: dict[str, dict] = {}
    windows: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)

    def add(zone_id: str, m3: float | None, estimated: bool, has_gaps: bool) -> None:
        row = totals.setdefault(
            zone_id,
            {"zone_id": zone_id, "m3": None, "water_is_estimate": False, "water_has_gaps": False},
        )
        if m3 is not None:
            row["m3"] = (row["m3"] or 0) + m3
            row["water_is_estimate"] |= estimated
        row["water_has_gaps"] |= has_gaps or m3 is None

    for zone, started, ended, amount, estimate, has_gaps in cycles:
        started = as_utc(started)
        ended = as_utc(ended) if ended else None
        known = known_cycle_water(amount, estimate)
        if since <= started and ended is not None and ended <= now_farm and known is not None:
            add(zone, known, estimate, has_gaps)
        else:
            windows[zone].append((max(since, started), min(now_farm, ended or now_farm)))

    # An observation just before midnight can support interpolation into today's range.
    cutoff = since - timedelta(seconds=max_gap_s(360))
    query = select(
        TelemetryPoint.zone_id,
        TelemetryPoint.ts,
        TelemetryPoint.value_numeric,
        TelemetryPoint.value_text,
        TelemetryPoint.quality,
        TelemetryPoint.source,
    ).where(
        TelemetryPoint.metric_key == "zone.flow_m3h",
        TelemetryPoint.zone_id.is_not(None),
        TelemetryPoint.ts >= cutoff,
        TelemetryPoint.ts <= now_farm,
    )
    recorded_only = totals.keys() - windows.keys()
    if recorded_only:
        query = query.where(TelemetryPoint.zone_id.not_in(recorded_only))
    generated = await generated_flow_timestamps(db, cutoff, now_farm)
    samples: dict[str, list[FlowSample]] = defaultdict(list)
    for zone, stamp, rate, speed, quality, source in await db.execute(
        query.order_by(TelemetryPoint.zone_id, TelemetryPoint.ts, TelemetryPoint.id)
    ):
        if source == "simulator" and (zone, as_utc(stamp)) in generated:
            continue
        samples[zone].append((stamp, rate, speed, quality))

    for zone in windows.keys() | samples.keys():
        for start, stop in windows.get(zone, [(since, now_farm)]):
            volume = integrate_flow(samples[zone], start, stop)
            add(zone, volume.m3, False, volume.has_gaps(start, stop))
    for row in totals.values():
        if row["m3"] is not None:
            row["m3"] = round(row["m3"], 3)
    return sorted(totals.values(), key=lambda row: row["zone_id"])


async def prune_old(db: AsyncSession) -> None:
    cutoff = clock.farm_now() - timedelta(days=settings.telemetry_retention_days)
    await db.execute(delete(TelemetryPoint).where(TelemetryPoint.ts < cutoff))
    await db.commit()
    await downsample_old(db)


DOWNSAMPLE_WINDOW = timedelta(hours=6)


async def downsample_old(db: AsyncSession) -> int:
    """Keep one sample per metric/zone/bucket for data older than the downsample age.

    Recent data stays at full resolution; older data (for 24 h / 7 d charts) is thinned
    so the table does not grow without bound between prunes.

    G7: works in 6-hour slices and commits after each one. A single statement over the
    whole table held SQLite's write lock for 15+ s on a busy farm PC, so the simulator's
    state pushes failed with "database is locked".
    """
    before = clock.farm_now() - timedelta(hours=settings.telemetry_downsample_after_hours)
    bucket = max(1, settings.telemetry_downsample_bucket_sec)
    sqlite = db.bind.dialect.name == "sqlite"
    if sqlite:
        epoch = "CAST(strftime('%s', ts) AS INTEGER)"
    else:  # PostgreSQL
        epoch = "CAST(EXTRACT(EPOCH FROM ts) AS BIGINT)"

    def bind(t: datetime):
        return t.replace(tzinfo=None) if sqlite else t

    oldest = (
        await db.execute(
            select(TelemetryPoint.ts)
            .where(TelemetryPoint.ts < bind(before))
            .order_by(TelemetryPoint.ts)
            .limit(1)
        )
    ).scalar()
    if oldest is None:
        return 0
    start = as_utc(oldest) if sqlite else oldest
    removed = 0
    while start < before:
        end = min(before, start + DOWNSAMPLE_WINDOW)
        res = await db.execute(
            text(
                f"""
                DELETE FROM telemetry_points
                WHERE ts >= :start AND ts < :end AND id NOT IN (
                    SELECT MIN(id) FROM telemetry_points
                    WHERE ts >= :start AND ts < :end
                    GROUP BY metric_key, COALESCE(zone_id, ''), {epoch} / :bucket
                )
                """
            ),
            {"start": bind(start), "end": bind(end), "bucket": bucket},
        )
        await db.commit()  # release the write lock between slices
        removed += res.rowcount or 0
        start = end
    return removed


recorder = Recorder()
