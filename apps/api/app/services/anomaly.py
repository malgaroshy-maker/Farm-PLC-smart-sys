"""
Statistical Anomaly Detection Service (Milestone E).

Performs per-zone statistical anomaly detection on flow (m³/h) and pressure (bar)
using robust statistics (median + MAD / modified z-score) calculated from completed cycles.
No LLM is used.

Key capabilities:
  1. Baselines: Computed per zone from completed cycles (outcome == 'completed').
     Requires a minimum number of baseline runs (default N=3) before alerting.
  2. Live evaluation while a zone runs:
     - High flow + low pressure -> Possible leak (ALM-046, S2)
     - Low flow + high pressure -> Clogged emitters (ALM-047, S2)
  3. Transient filtering:
     - Startup grace period suppresses initial valve opening pressure waves.
     - Debounce timer ensures transient fluctuations do not raise false alarms.
"""

import logging
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.services.alarms import Condition
from app.services.live_state import Snapshot

log = logging.getLogger(__name__)

# Standard scale factor for normal distribution consistency with MAD:
# 1 / Phi^(-1)(0.75) ≈ 1.4826
NORMAL_CONSISTENT_MAD_SCALE = 1.4826

# Alarm codes owned by the anomaly detector
ALM_LEAK = "ALM-046"
ALM_CLOGGED = "ALM-047"


@dataclass(frozen=True)
class BaselineStats:
    """Robust statistical parameters for a metric."""

    median: float
    mad: float
    scale: float
    count: int

    def robust_z_score(self, val: float) -> float:
        """Calculate robust modified z-score for an observed value."""
        if self.scale <= 0.0:
            return 0.0
        return (val - self.median) / self.scale


@dataclass(frozen=True)
class ZoneBaseline:
    """Established hydraulic baseline for an irrigation zone."""

    zone_id: str
    flow: BaselineStats
    pressure: BaselineStats
    runs_count: int
    computed_at: datetime


@dataclass
class AnomalyEvaluation:
    """Detailed result of a live zone evaluation."""

    zone_id: str
    flow_m3h: float
    pressure_bar: float
    flow_z_score: float
    pressure_z_score: float
    is_leak: bool
    is_clogged: bool
    alarm_code: str | None
    detail: str


def compute_baseline_stats(
    values: list[float],
    min_scale_ratio: float = 0.05,
    min_scale_floor: float = 0.05,
) -> BaselineStats:
    """Calculate median, MAD, and robust scale factor for a sample of measurements."""
    if not values:
        return BaselineStats(median=0.0, mad=0.0, scale=min_scale_floor, count=0)

    med = float(statistics.median(values))
    deviations = [abs(v - med) for v in values]
    mad = float(statistics.median(deviations))

    # Scale with floor to prevent zero division when all baseline samples are identical
    effective_scale = max(
        mad * NORMAL_CONSISTENT_MAD_SCALE,
        abs(med) * min_scale_ratio,
        min_scale_floor,
    )
    return BaselineStats(median=med, mad=mad, scale=effective_scale, count=len(values))


def compute_baseline_from_samples(
    zone_id: str,
    flows: list[float],
    pressures: list[float],
    min_runs: int = 3,
) -> ZoneBaseline | None:
    """Build a ZoneBaseline if at least min_runs samples are available."""
    if len(flows) < min_runs or len(pressures) < min_runs:
        return None
    flow_stats = compute_baseline_stats(flows, min_scale_ratio=0.05, min_scale_floor=0.1)
    press_stats = compute_baseline_stats(pressures, min_scale_ratio=0.05, min_scale_floor=0.05)
    return ZoneBaseline(
        zone_id=zone_id,
        flow=flow_stats,
        pressure=press_stats,
        runs_count=min(len(flows), len(pressures)),
        computed_at=clock.farm_now(),
    )


class AnomalyDetector:
    """
    Evaluates running irrigation zones for hydraulic anomalies using robust statistics.
    """

    def __init__(
        self,
        min_baseline_runs: int = 3,
        z_threshold: float = 2.0,
        debounce_sec: float = 3.0,
        startup_grace_sec: float = 4.0,
    ) -> None:
        self.min_baseline_runs = min_baseline_runs
        self.z_threshold = z_threshold
        self.debounce_sec = debounce_sec
        self.startup_grace_sec = startup_grace_sec

        # Cached baselines per zone_id
        self._baselines: dict[str, ZoneBaseline] = {}
        # Debounce tracking: key -> first_seen_datetime
        self._pending_anomalies: dict[str, datetime] = {}

    def reset(self) -> None:
        """Clear all in-memory baselines and pending debounce timers."""
        self._baselines.clear()
        self._pending_anomalies.clear()

    def get_baseline(self, zone_id: str) -> ZoneBaseline | None:
        return self._baselines.get(zone_id)

    def set_baseline(self, baseline: ZoneBaseline) -> None:
        self._baselines[baseline.zone_id] = baseline

    def clear_baseline(self, zone_id: str | None = None) -> None:
        if zone_id:
            self._baselines.pop(zone_id, None)
        else:
            self._baselines.clear()

    async def compute_zone_baseline_from_db(
        self,
        db: AsyncSession,
        zone_id: str,
        max_cycles: int = 20,
    ) -> ZoneBaseline | None:
        """
        Query completed cycles and train on paired flow and pressure telemetry.
        """
        res = await db.execute(
            select(IrrigationCycle)
            .where(
                IrrigationCycle.zone_id == zone_id,
                IrrigationCycle.outcome == "completed",
                # Legacy demo scenarios inserted cycles with this reserved prefix.
                ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
            )
            .order_by(desc(IrrigationCycle.actual_end_at))
            .limit(max_cycles)
        )
        completed = res.scalars().all()
        if len(completed) < self.min_baseline_runs:
            return None

        flows: list[float] = []
        pressures: list[float] = []

        for cycle in completed:
            if not cycle.actual_start_at or not cycle.actual_end_at:
                continue
            start_utc = as_utc(cycle.actual_start_at)
            end_utc = as_utc(cycle.actual_end_at)

            # Query telemetry during this cycle
            pts_res = await db.execute(
                select(TelemetryPoint.metric_key, TelemetryPoint.value_numeric)
                .where(
                    TelemetryPoint.ts >= start_utc,
                    TelemetryPoint.ts <= end_utc,
                    TelemetryPoint.metric_key.in_(
                        ("zone.flow_m3h", "zone.pressure_bar", "main_flow_m3h", "main_pressure_bar")
                    ),
                )
                .where((TelemetryPoint.zone_id == zone_id) | (TelemetryPoint.zone_id.is_(None)))
            )
            pts = pts_res.all()

            cycle_flows = [
                v
                for k, v in pts
                if k in ("zone.flow_m3h", "main_flow_m3h") and v is not None and v > 0
            ]
            cycle_press = [
                v
                for k, v in pts
                if k in ("zone.pressure_bar", "main_pressure_bar") and v is not None and v > 0
            ]

            if cycle_flows and cycle_press:
                flows.append(float(statistics.median(cycle_flows)))
                pressures.append(float(statistics.median(cycle_press)))

        baseline = compute_baseline_from_samples(
            zone_id, flows, pressures, min_runs=self.min_baseline_runs
        )
        if baseline:
            self.set_baseline(baseline)
        return baseline

    async def get_or_load_baseline(
        self,
        db: AsyncSession,
        zone_id: str,
    ) -> ZoneBaseline | None:
        """Return cached baseline or compute it from database completed cycles."""
        bl = self.get_baseline(zone_id)
        if bl is not None:
            return bl
        return await self.compute_zone_baseline_from_db(db, zone_id)

    def evaluate_readings(
        self,
        zone_id: str,
        flow_m3h: float,
        pressure_bar: float,
        runtime_sec: float,
        baseline: ZoneBaseline | None,
        now: datetime,
    ) -> AnomalyEvaluation:
        """
        Evaluate raw flow and pressure against zone baseline with transient filtering.
        """
        # If no baseline established (insufficient completed cycles), return no anomaly
        if baseline is None:
            return AnomalyEvaluation(
                zone_id=zone_id,
                flow_m3h=flow_m3h,
                pressure_bar=pressure_bar,
                flow_z_score=0.0,
                pressure_z_score=0.0,
                is_leak=False,
                is_clogged=False,
                alarm_code=None,
                detail="insufficient baseline runs",
            )

        # Transient suppression: during initial valve travel / filling, ignore pressure waves
        if runtime_sec < self.startup_grace_sec:
            return AnomalyEvaluation(
                zone_id=zone_id,
                flow_m3h=flow_m3h,
                pressure_bar=pressure_bar,
                flow_z_score=0.0,
                pressure_z_score=0.0,
                is_leak=False,
                is_clogged=False,
                alarm_code=None,
                detail=f"startup grace period active ({runtime_sec:.1f}s < {self.startup_grace_sec}s)",
            )

        z_flow = baseline.flow.robust_z_score(flow_m3h)
        z_press = baseline.pressure.robust_z_score(pressure_bar)

        # High flow + low pressure -> possible leak (ALM-046)
        is_leak = (z_flow >= self.z_threshold) and (z_press <= -self.z_threshold)

        # Low flow + high pressure -> clogged emitters (ALM-047)
        is_clogged = (z_flow <= -self.z_threshold) and (z_press >= self.z_threshold)

        alarm_code = None
        detail = ""
        if is_leak:
            alarm_code = ALM_LEAK
            detail = (
                f"high flow ({flow_m3h:.2f} m³/h, z={z_flow:.1f}) + "
                f"low pressure ({pressure_bar:.2f} bar, z={z_press:.1f}) "
                f"[base: Q={baseline.flow.median:.2f}, P={baseline.pressure.median:.2f}]"
            )
        elif is_clogged:
            alarm_code = ALM_CLOGGED
            detail = (
                f"low flow ({flow_m3h:.2f} m³/h, z={z_flow:.1f}) + "
                f"high pressure ({pressure_bar:.2f} bar, z={z_press:.1f}) "
                f"[base: Q={baseline.flow.median:.2f}, P={baseline.pressure.median:.2f}]"
            )

        return AnomalyEvaluation(
            zone_id=zone_id,
            flow_m3h=flow_m3h,
            pressure_bar=pressure_bar,
            flow_z_score=z_flow,
            pressure_z_score=z_press,
            is_leak=is_leak,
            is_clogged=is_clogged,
            alarm_code=alarm_code,
            detail=detail,
        )

    def _debounce(
        self,
        key: str,
        active: bool,
        now: datetime,
    ) -> bool:
        """
        Debounce timer implementation. Returns True only when condition persists >= debounce_sec.
        """
        if not active:
            self._pending_anomalies.pop(key, None)
            return False
        if self.debounce_sec <= 0.0:
            return True
        since = self._pending_anomalies.setdefault(key, now)
        elapsed = (now - since).total_seconds()
        return elapsed >= self.debounce_sec

    async def evaluate_snapshots(
        self,
        db: AsyncSession,
        snapshots: dict[str, Snapshot],
        now: datetime,
        real_now: datetime | None = None,
    ) -> list[Condition]:
        """
        Main entry point called on live state synchronization.
        Inspects running zones, evaluates flow and pressure against baselines,
        applies debounce timers, and returns active alarm Conditions.
        """
        r_now = real_now or utcnow()
        stats = snapshots.get("simulation_stats")
        main_flow = float(stats.state.get("main_flow_m3h", 0.0)) if stats else 0.0
        main_press = float(stats.state.get("main_pressure_bar", 0.0)) if stats else 0.0

        running_zones: list[tuple[str, dict[str, Any]]] = []
        for key, snap in snapshots.items():
            if key.startswith("zone_"):
                st = snap.state
                if st.get("state") == "running":
                    zid = st.get("zone_id")
                    if zid:
                        running_zones.append((zid, st))

        # Clear debounce timers for zones no longer running
        active_zone_ids = {zid for zid, _ in running_zones}
        for k in list(self._pending_anomalies):
            parts = k.split(":")
            if len(parts) >= 2 and parts[1] not in active_zone_ids:
                self._pending_anomalies.pop(k, None)

        if not running_zones:
            return []

        conditions: list[Condition] = []

        for zid, zstate in running_zones:
            baseline = await self.get_or_load_baseline(db, zid)
            if baseline is None:
                # If zone has no baseline in DB yet, check if zone config exists
                # and no completed cycles exist yet -> no alert
                continue

            runtime_sec = float(zstate.get("runtime_sec", 0.0))
            zone_flow = float(zstate.get("flow_m3h", 0.0))
            zone_press = float(zstate.get("pressure_bar", 0.0))

            # When a single zone is running on the mainline (standard operation & leak scenario):
            # Mainline flow captures pipe bursts between pump and zone.
            eval_flow = main_flow if (len(running_zones) == 1 and main_flow > 0) else zone_flow
            eval_press = main_press if (len(running_zones) == 1 and main_press > 0) else zone_press

            eval_res = self.evaluate_readings(
                zone_id=zid,
                flow_m3h=eval_flow,
                pressure_bar=eval_press,
                runtime_sec=runtime_sec,
                baseline=baseline,
                now=now,
            )

            leak_key = f"{ALM_LEAK}:{zid}"
            clogged_key = f"{ALM_CLOGGED}:{zid}"

            leak_debounced = self._debounce(leak_key, eval_res.is_leak, r_now)
            clogged_debounced = self._debounce(clogged_key, eval_res.is_clogged, r_now)

            if leak_debounced:
                conditions.append(
                    Condition(
                        code=ALM_LEAK,
                        zone_id=zid,
                        value=round(eval_flow, 2),
                        threshold=round(baseline.flow.median, 2),
                        detail=eval_res.detail,
                    )
                )

            if clogged_debounced:
                conditions.append(
                    Condition(
                        code=ALM_CLOGGED,
                        zone_id=zid,
                        value=round(eval_flow, 2),
                        threshold=round(baseline.flow.median, 2),
                        detail=eval_res.detail,
                    )
                )

        return conditions


# Global anomaly detector instance
anomaly_detector = AnomalyDetector()
