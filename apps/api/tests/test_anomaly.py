"""
Test suite for Statistical Anomaly Detection Service (Milestone E).

Validates:
  1. Statistical baseline calculations (median, MAD, robust z-score, minimum runs requirement).
  2. Database baseline computation from completed cycles.
  3. Live anomaly detection rules:
     - High flow + low pressure -> ALM-046 (Possible leak, S2)
     - Low flow + high pressure -> ALM-047 (Possible clogged emitters, S2)
     - Other patterns (high+high, low+low) do not raise leak or clogged alarms.
  4. Transient valve opening pressure wave suppression (startup grace period).
  5. Debounce timer verification (transients do not latch; persistent conditions do).
  6. Integration with AlarmEngine and on_state_sync.
  7. Leak scenario vs normal cycle verification.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from conftest import push_state
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.models.zone import Zone
from app.services.anomaly import (
    ALM_CLOGGED,
    ALM_LEAK,
    AnomalyDetector,
    compute_baseline_from_samples,
    compute_baseline_stats,
)


async def add_baseline_test_cycles(
    db: AsyncSession,
    zone_id: str,
    n_runs: int = 3,
) -> list[IrrigationCycle]:
    """Create baseline fixtures in the isolated test database."""
    res = await db.execute(
        select(IrrigationCycle).where(
            IrrigationCycle.zone_id == zone_id,
            IrrigationCycle.outcome == "completed",
        )
    )
    existing = list(res.scalars().all())
    needed = n_runs - len(existing)
    if needed <= 0:
        return existing

    zone_row = await db.get(Zone, zone_id)
    flow = ((zone_row.flow_min_m3h + zone_row.flow_max_m3h) / 2.0) if zone_row else 10.0
    pressure = ((zone_row.pressure_min_bar + zone_row.pressure_max_bar) / 2.0) if zone_row else 2.8

    now = clock.farm_now()
    created: list[IrrigationCycle] = []
    for i in range(needed):
        start = now - timedelta(days=needed - i, minutes=30)
        end = now - timedelta(days=needed - i)
        cyc = IrrigationCycle(
            id=f"cyc_test_{zone_id[:8]}_{i}_{uuid4().hex[:6]}",
            zone_id=zone_id,
            source_mode="tank",
            actual_start_at=start,
            actual_end_at=end,
            planned_duration_min=30,
            actual_duration_min=30,
            outcome="completed",
            water_estimate_m3=round(flow * 0.5, 4),
            water_is_estimate=False,
            created_at=start,
            updated_at=end,
        )
        db.add(cyc)
        created.append(cyc)

        for offset_s in (30, 300, 600, 900, 1200, 1500):
            pt_ts = start + timedelta(seconds=offset_s)
            db.add(
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_algaroshy",
                    zone_id=zone_id,
                    ts=pt_ts,
                    value_numeric=flow,
                    value_text="1.0",
                    source="simulator",
                )
            )
            db.add(
                TelemetryPoint(
                    metric_key="zone.pressure_bar",
                    farm_id="farm_algaroshy",
                    zone_id=zone_id,
                    ts=pt_ts,
                    value_numeric=pressure,
                    value_text="1.0",
                    source="simulator",
                )
            )

    await db.commit()
    # Invalidate cache so new cycles are loaded
    return existing + created


# ── 1. Statistical Math Unit Tests ──────────────────────────────────────────


def test_compute_baseline_stats_known_values():
    # Symmetric distribution around 10.0: [8, 9, 10, 11, 12]
    # Median = 10.0, deviations = [2, 1, 0, 1, 2], MAD = 1.0
    # scale = 1.4826 * 1.0 = 1.4826
    stats = compute_baseline_stats([8.0, 9.0, 10.0, 11.0, 12.0])
    assert stats.median == 10.0
    assert stats.mad == 1.0
    assert stats.scale == pytest.approx(1.4826, rel=1e-3)
    assert stats.count == 5

    # Z-scores:
    # Value 10.0 -> z = 0
    assert stats.robust_z_score(10.0) == 0.0
    # Value 12.9652 -> (12.9652 - 10) / 1.4826 = 2.0
    assert stats.robust_z_score(10.0 + 2.0 * 1.4826) == pytest.approx(2.0, rel=1e-3)
    # Value 7.0348 -> (7.0348 - 10) / 1.4826 = -2.0
    assert stats.robust_z_score(10.0 - 2.0 * 1.4826) == pytest.approx(-2.0, rel=1e-3)


def test_compute_baseline_stats_constant_values():
    # Constant values: MAD = 0. Must not divide by zero; floor scale applied.
    stats = compute_baseline_stats([10.0, 10.0, 10.0, 10.0])
    assert stats.median == 10.0
    assert stats.mad == 0.0
    assert stats.scale > 0.0
    # A small perturbation does not blow up to infinity
    z = stats.robust_z_score(10.5)
    assert abs(z) < 10.0


def test_baseline_insufficient_runs():
    # Fewer than min_runs (default 3) returns None
    assert compute_baseline_from_samples("zone_a", [10.0], [2.5], min_runs=3) is None
    assert compute_baseline_from_samples("zone_a", [10.0, 10.2], [2.5, 2.6], min_runs=3) is None

    # Exactly 3 runs returns a valid ZoneBaseline
    b = compute_baseline_from_samples("zone_a", [10.0, 10.2, 9.8], [2.5, 2.6, 2.4], min_runs=3)
    assert b is not None
    assert b.zone_id == "zone_a"
    assert b.flow.count == 3
    assert b.pressure.count == 3
    assert b.flow.median == 10.0
    assert b.pressure.median == 2.5


# ── 2. Live Evaluation Rules (Leak vs Clogged) ───────────────────────────────


def test_live_evaluation_normal_flow_and_pressure():
    detector = AnomalyDetector(min_baseline_runs=3, z_threshold=2.0)
    baseline = compute_baseline_from_samples(
        "zone_test", [10.0, 10.1, 9.9, 10.0], [2.8, 2.9, 2.7, 2.8], min_runs=3
    )

    now = datetime.now()
    res = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=10.05,
        pressure_bar=2.82,
        runtime_sec=20.0,
        baseline=baseline,
        now=now,
    )
    assert not res.is_leak
    assert not res.is_clogged
    assert res.alarm_code is None


def test_live_evaluation_possible_leak_alm046():
    # High flow + low pressure -> ALM-046
    detector = AnomalyDetector(min_baseline_runs=3, z_threshold=2.0)
    baseline = compute_baseline_from_samples(
        "zone_test", [10.0, 10.1, 9.9, 10.0], [2.8, 2.9, 2.7, 2.8], min_runs=3
    )

    now = datetime.now()
    # Flow = 16.0 (way above 10.0), Pressure = 1.8 (way below 2.8)
    res = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=16.0,
        pressure_bar=1.8,
        runtime_sec=20.0,
        baseline=baseline,
        now=now,
    )
    assert res.is_leak
    assert not res.is_clogged
    assert res.alarm_code == ALM_LEAK
    assert res.flow_z_score >= 2.0
    assert res.pressure_z_score <= -2.0


def test_live_evaluation_clogged_emitters_alm047():
    # Low flow + high pressure -> ALM-047
    detector = AnomalyDetector(min_baseline_runs=3, z_threshold=2.0)
    baseline = compute_baseline_from_samples(
        "zone_test", [10.0, 10.1, 9.9, 10.0], [2.8, 2.9, 2.7, 2.8], min_runs=3
    )

    now = datetime.now()
    # Flow = 4.0 (well below baseline), Pressure = 3.8 (well above baseline)
    res = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=4.0,
        pressure_bar=3.8,
        runtime_sec=20.0,
        baseline=baseline,
        now=now,
    )
    assert not res.is_leak
    assert res.is_clogged
    assert res.alarm_code == ALM_CLOGGED
    assert res.flow_z_score <= -2.0
    assert res.pressure_z_score >= 2.0


def test_live_evaluation_high_high_and_low_low_no_alarm():
    detector = AnomalyDetector(min_baseline_runs=3, z_threshold=2.0)
    baseline = compute_baseline_from_samples(
        "zone_test", [10.0, 10.1, 9.9], [2.8, 2.9, 2.7], min_runs=3
    )
    now = datetime.now()

    # High flow + High pressure (e.g. pump supply surge) -> NOT a leak and NOT clogged
    res_high_high = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=16.0,
        pressure_bar=4.0,
        runtime_sec=30.0,
        baseline=baseline,
        now=now,
    )
    assert not res_high_high.is_leak
    assert not res_high_high.is_clogged
    assert res_high_high.alarm_code is None

    # Low flow + Low pressure (e.g. supply starved/empty tank) -> NOT a leak and NOT clogged
    res_low_low = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=2.0,
        pressure_bar=0.8,
        runtime_sec=30.0,
        baseline=baseline,
        now=now,
    )
    assert not res_low_low.is_leak
    assert not res_low_low.is_clogged
    assert res_low_low.alarm_code is None


# ── 3. Transient Wave Suppression & Debounce Timers ─────────────────────────


def test_startup_grace_period_suppresses_transient_waves():
    # During startup (runtime_sec < startup_grace_sec), pressure waves occur.
    # Must suppress anomaly evaluation even with extreme values.
    detector = AnomalyDetector(min_baseline_runs=3, startup_grace_sec=5.0)
    baseline = compute_baseline_from_samples("zone_test", [10.0, 10.0, 10.0], [2.8, 2.8, 2.8])

    now = datetime.now()
    # At runtime_sec = 2.0s (< 5.0s grace period)
    res = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=25.0,
        pressure_bar=0.5,
        runtime_sec=2.0,
        baseline=baseline,
        now=now,
    )
    assert not res.is_leak
    assert res.alarm_code is None
    assert "startup grace period active" in res.detail

    # Once runtime_sec = 6.0s (past grace period), anomaly is flagged
    res_settled = detector.evaluate_readings(
        zone_id="zone_test",
        flow_m3h=25.0,
        pressure_bar=0.5,
        runtime_sec=6.0,
        baseline=baseline,
        now=now,
    )
    assert res_settled.is_leak
    assert res_settled.alarm_code == ALM_LEAK


def test_debounce_timer_behavior():
    detector = AnomalyDetector(debounce_sec=3.0)
    key = "ALM-046:zone_test"
    t0 = datetime(2026, 6, 1, 10, 0, 0)

    # First observation at t0: timer starts, not yet active
    assert not detector._debounce(key, active=True, now=t0)

    # After 1.5 seconds: still pending
    t1 = t0 + timedelta(seconds=1.5)
    assert not detector._debounce(key, active=True, now=t1)

    # After 3.0 seconds: debounce threshold satisfied -> True
    t2 = t0 + timedelta(seconds=3.0)
    assert detector._debounce(key, active=True, now=t2)

    # Condition drops (false): timer is discarded
    assert not detector._debounce(key, active=False, now=t2 + timedelta(seconds=1.0))

    # Condition re-occurs: timer restarts from new timestamp
    t3 = t0 + timedelta(seconds=10.0)
    assert not detector._debounce(key, active=True, now=t3)
    assert detector._debounce(key, active=True, now=t3 + timedelta(seconds=3.0))


# ── 4. Database Baseline & Seed Runs ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_baseline_runs_and_db_computation(client):
    async with async_session_factory() as db:
        zone_id = "zone_zaytoun"

        # Initially 0 completed cycles
        bl = await AnomalyDetector(min_baseline_runs=3).compute_zone_baseline_from_db(db, zone_id)
        assert bl is None

        # Seed baseline runs
        cycles = await add_baseline_test_cycles(db, zone_id, n_runs=3)
        assert len(cycles) >= 3

        # Now baseline is successfully computed
        detector = AnomalyDetector(min_baseline_runs=3)
        bl = await detector.compute_zone_baseline_from_db(db, zone_id)
        assert bl is not None
        assert bl.zone_id == zone_id
        assert bl.runs_count >= 3
        assert bl.flow.median > 0
        assert bl.pressure.median > 0

        for cycle in cycles:
            cycle.id = cycle.id.replace("cyc_test_", "cyc_base_", 1)
        await db.commit()
        assert await detector.compute_zone_baseline_from_db(db, zone_id) is None


# ── 5. Integration with State Sync & AlarmEngine ────────────────────────────


@pytest.mark.asyncio
async def test_normal_cycle_does_not_trigger_leak_or_clogged_alarms(client):
    zone_id = "zone_rumman_1"

    # Establish baseline
    async with async_session_factory() as db:
        await add_baseline_test_cycles(db, zone_id, n_runs=3)

    # Push state with normal flow and pressure while zone is running
    push_state(
        client,
        zone_states={zone_id: "running"},
        pressure=2.8,
    )

    async with async_session_factory() as db:
        # Check active alarms
        alarms_res = await db.execute(
            select(Alarm).where(
                Alarm.alarm_code.in_([ALM_LEAK, ALM_CLOGGED]),
                Alarm.status.in_(["active_unacked", "active_acked"]),
            )
        )
        active = alarms_res.scalars().all()
        assert len(active) == 0


@pytest.mark.asyncio
async def test_state_sync_triggers_alm046_on_leak(client):
    zone_id = "zone_zaytoun"

    # Establish baseline
    async with async_session_factory() as db:
        await add_baseline_test_cycles(db, zone_id, n_runs=3)

    # Set alarm debounce to 0 in detector for direct test
    from app.services.anomaly import anomaly_detector

    anomaly_detector.debounce_sec = 0.0
    anomaly_detector.startup_grace_sec = 0.0

    now_iso = utcnow().isoformat()
    # Push leak state: high mainline flow (19.0 m3/h) + low mainline pressure (1.9 bar)
    payloads = [
        {"device_key": "system_mode", "state_json": {"mode": "auto"}, "updated_at": now_iso},
        {
            "device_key": "simulation_stats",
            "state_json": {
                "tank_level_pct": 80.0,
                "main_pressure_bar": 1.9,
                "main_flow_m3h": 19.0,
            },
            "updated_at": now_iso,
        },
        {
            "device_key": f"zone_{zone_id}",
            "state_json": {
                "zone_id": zone_id,
                "state": "running",
                "health": "healthy",
                "source_mode": "tank",
                "moisture_pct": 40.0,
                "flow_m3h": 8.0,
                "pressure_bar": 1.7,
                "runtime_sec": 30.0,
                "last_updated": now_iso,
            },
            "updated_at": now_iso,
        },
    ]

    r = client.post(
        "/api/v1/state/sync", json=payloads, headers={"Authorization": "Bearer test-sim-token"}
    )
    assert r.status_code == 200

    # ALM-046 should be active in the alarm catalog and database
    async with async_session_factory() as db:
        res = await db.execute(select(Alarm).where(Alarm.alarm_code == ALM_LEAK))
        alarm = res.scalars().first()
        assert alarm is not None
        assert alarm.status == "active_unacked"
        assert alarm.severity == "S2"
        assert alarm.category == "process"
        assert alarm.zone_id == zone_id
        from app.core.alarm_catalog import CATALOG

        spec = CATALOG[alarm.alarm_code]
        assert spec.name == "Possible leak"
        assert spec.name_ar == "تسريب محتمل في الخط الرئيسي"
        assert "leak" in alarm.message_en.lower()
        assert "تسريب" in alarm.message_ar

    # Now clear leak by returning to normal readings
    payloads_normal = [
        {"device_key": "system_mode", "state_json": {"mode": "auto"}, "updated_at": now_iso},
        {
            "device_key": "simulation_stats",
            "state_json": {
                "tank_level_pct": 80.0,
                "main_pressure_bar": 2.8,
                "main_flow_m3h": 10.0,
            },
            "updated_at": now_iso,
        },
        {
            "device_key": f"zone_{zone_id}",
            "state_json": {
                "zone_id": zone_id,
                "state": "running",
                "health": "healthy",
                "source_mode": "tank",
                "moisture_pct": 40.0,
                "flow_m3h": 10.0,
                "pressure_bar": 2.8,
                "runtime_sec": 60.0,
                "last_updated": now_iso,
            },
            "updated_at": now_iso,
        },
    ]
    r = client.post(
        "/api/v1/state/sync",
        json=payloads_normal,
        headers={"Authorization": "Bearer test-sim-token"},
    )
    assert r.status_code == 200

    async with async_session_factory() as db:
        res = await db.execute(select(Alarm).where(Alarm.alarm_code == ALM_LEAK))
        alarm = res.scalars().first()
        # Alarm requires_ack=True, so when cleared while unacked, it remains active_unacked or clears upon ack
        assert alarm.cleared_at is not None


@pytest.mark.asyncio
async def test_state_sync_triggers_alm047_on_clogged_emitters(client):
    zone_id = "zone_rumman_2"

    async with async_session_factory() as db:
        await add_baseline_test_cycles(db, zone_id, n_runs=3)

    from app.services.anomaly import anomaly_detector

    anomaly_detector.debounce_sec = 0.0
    anomaly_detector.startup_grace_sec = 0.0

    now_iso = utcnow().isoformat()
    # Push clogged emitter state: low flow (2.0 m3/h) + high pressure (3.9 bar)
    payloads = [
        {"device_key": "system_mode", "state_json": {"mode": "auto"}, "updated_at": now_iso},
        {
            "device_key": "simulation_stats",
            "state_json": {
                "tank_level_pct": 80.0,
                "main_pressure_bar": 3.9,
                "main_flow_m3h": 2.0,
            },
            "updated_at": now_iso,
        },
        {
            "device_key": f"zone_{zone_id}",
            "state_json": {
                "zone_id": zone_id,
                "state": "running",
                "health": "healthy",
                "source_mode": "tank",
                "moisture_pct": 40.0,
                "flow_m3h": 2.0,
                "pressure_bar": 3.9,
                "runtime_sec": 30.0,
                "last_updated": now_iso,
            },
            "updated_at": now_iso,
        },
    ]

    r = client.post(
        "/api/v1/state/sync", json=payloads, headers={"Authorization": "Bearer test-sim-token"}
    )
    assert r.status_code == 200

    async with async_session_factory() as db:
        res = await db.execute(select(Alarm).where(Alarm.alarm_code == ALM_CLOGGED))
        alarm = res.scalars().first()
        assert alarm is not None
        assert alarm.status == "active_unacked"
        assert alarm.severity == "S2"
        assert alarm.category == "process"
        assert alarm.zone_id == zone_id
        from app.core.alarm_catalog import CATALOG

        spec = CATALOG[alarm.alarm_code]
        assert spec.name == "Possible clogged emitters"
        assert spec.name_ar == "انسداد محتمل في النقاطات"
        assert "clogged" in alarm.message_en.lower()
        assert "انسداد" in alarm.message_ar


# ── 6. Scenario Verification: Leak vs Normal Cycle ──────────────────────────


def test_scenario_definitions_for_anomaly_alarms():
    from app.services.scenarios import SCENARIOS

    # The PLC protection scenario works without a statistical baseline.
    assert "mainline_leak" in SCENARIOS
    leak_scen = SCENARIOS["mainline_leak"]
    assert leak_scen.expect == ["ALM-013"]

    # normal_cycle must NOT expect ALM-046 or ALM-047
    assert "normal_cycle" in SCENARIOS
    normal_scen = SCENARIOS["normal_cycle"]
    assert "ALM-046" not in normal_scen.expect
    assert "ALM-047" not in normal_scen.expect


@pytest.mark.asyncio
async def test_leak_scenario_flow_triggers_alm046_and_normal_does_not(client):
    zone_id = "zone_zaytoun"
    async with async_session_factory() as db:
        await add_baseline_test_cycles(db, zone_id, n_runs=3)

    from app.services.anomaly import anomaly_detector

    anomaly_detector.debounce_sec = 0.0
    anomaly_detector.startup_grace_sec = 0.0

    # Step 1: Normal cycle run -> verify neither alarm triggers
    push_state(
        client,
        zone_states={zone_id: "running"},
        pressure=2.8,
    )
    async with async_session_factory() as db:
        res = await db.execute(
            select(Alarm).where(
                Alarm.alarm_code.in_([ALM_LEAK, ALM_CLOGGED]),
                Alarm.status.in_(["active_unacked", "active_acked"]),
            )
        )
        assert len(res.scalars().all()) == 0

    # Step 2: Leak occurs -> high mainline flow + low mainline pressure
    # stamped now, not before step 1: the API ignores a reading older than the one it has
    now_iso = utcnow().isoformat()
    payloads_leak = [
        {"device_key": "system_mode", "state_json": {"mode": "auto"}, "updated_at": now_iso},
        {
            "device_key": "simulation_stats",
            "state_json": {
                "tank_level_pct": 80.0,
                "main_pressure_bar": 2.0,
                "main_flow_m3h": 18.5,
            },
            "updated_at": now_iso,
        },
        {
            "device_key": "plc_alarms",
            "state_json": {"active": [{"code": "ALM-013"}]},
            "updated_at": now_iso,
        },
        {
            "device_key": f"zone_{zone_id}",
            "state_json": {
                "zone_id": zone_id,
                "state": "running",
                "health": "healthy",
                "source_mode": "tank",
                "moisture_pct": 40.0,
                "flow_m3h": 9.5,
                "pressure_bar": 1.8,
                "runtime_sec": 45.0,
                "last_updated": now_iso,
            },
            "updated_at": now_iso,
        },
    ]
    r = client.post(
        "/api/v1/state/sync", json=payloads_leak, headers={"Authorization": "Bearer test-sim-token"}
    )
    assert r.status_code == 200

    # Both ALM-013 and ALM-046 are now active!
    async with async_session_factory() as db:
        res_046 = await db.execute(select(Alarm).where(Alarm.alarm_code == ALM_LEAK))
        alarm_046 = res_046.scalars().first()
        assert alarm_046 is not None
        assert alarm_046.status == "active_unacked"
        assert alarm_046.severity == "S2"

        res_013 = await db.execute(select(Alarm).where(Alarm.alarm_code == "ALM-013"))
        alarm_013 = res_013.scalars().first()
        assert alarm_013 is not None
