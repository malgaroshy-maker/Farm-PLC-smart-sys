"""Simulator behaviour tests: sequences, physics, and PLC protection (no API needed)."""

import pytest

from src.client import apply_layout
from src.engine import SimulatorEngine
from src.state import FarmSimulationState

ZONES = [
    {
        "id": "zone_a",
        "code": "A",
        "flow_min_m3h": 3.0,
        "flow_max_m3h": 10.0,
        "default_duration_min": 2,
    },
    {
        "id": "zone_b",
        "code": "B",
        "flow_min_m3h": 2.0,
        "flow_max_m3h": 8.0,
        "default_duration_min": 2,
    },
    {
        "id": "zone_w",
        "code": "W",
        "flow_min_m3h": 1.0,
        "flow_max_m3h": 4.0,
        "allows_direct_well": True,
        "default_duration_min": 2,
    },
]
PUMPS = [
    {"id": "pump_well_01", "pump_type": "well"},
    {"id": "pump_booster_01", "pump_type": "booster"},
]
VALVES = [{"id": f"valve_{z['code'].lower()}", "zone_id": z["id"]} for z in ZONES]
SENSORS = [
    {"id": "sensor_tank_level", "sensor_type": "level", "unit": "%"},
    {"id": "sensor_moisture_a", "sensor_type": "moisture", "zone_id": "zone_a", "unit": "%"},
]


@pytest.fixture()
def eng() -> SimulatorEngine:
    e = SimulatorEngine(FarmSimulationState(), seed=1)
    apply_layout(e, ZONES, PUMPS, VALVES, SENSORS)
    return e


def run(e: SimulatorEngine, seconds: float, dt: float = 0.5) -> None:
    for _ in range(int(seconds / dt)):
        e.step(dt)


def cmd(ctype, target=None, cid="c1", **payload):
    return {"id": cid, "command_type": ctype, "target_id": target, "payload": payload or None}


def fault(e, target_type, fault_type, target_id=None, value=None):
    [res] = e.process_commands(
        [
            cmd(
                "inject_fault",
                None,
                "f",
                target_type=target_type,
                target_id=target_id,
                fault_type=fault_type,
                value=value,
            )
        ]
    )
    assert res["status"] == "completed", res


def start(e, zone="zone_a"):
    return e.process_commands([cmd("start_zone", zone)])[0]


# ── Normal sequences ─────────────────────────────────────


def test_start_walks_through_timed_sequence(eng):
    assert start(eng)["status"] == "accepted"
    z, booster, valve = (
        eng.state.zones["zone_a"],
        eng.state.pumps["pump_booster_01"],
        eng.state.valves["valve_a"],
    )
    seen = set()
    for _ in range(60):
        eng.step(0.5)
        seen.add(z.state)
    assert {"starting_pump", "opening_valve", "validating_flow", "running"} <= seen
    assert booster.state == "running" and valve.status == "open"
    assert 3.0 <= z.flow_m3h <= 10.0, z.flow_m3h
    assert 1.5 <= z.pressure_bar <= 4.0, z.pressure_bar
    # command completes only once the zone is really running
    assert eng.drain_outbox()[0]["status"] == "completed"


def test_cycle_completes_at_duration_and_stops_pump(eng):
    start(eng)
    run(eng, 2 * 60 + 30)
    assert eng.state.zones["zone_a"].state == "completed"
    assert eng.state.pumps["pump_booster_01"].state == "stopped"
    assert eng.state.valves["valve_a"].status == "closed"


def test_irrigation_drains_tank_and_wets_soil(eng):
    tank0, moist0 = eng.true_tank_pct, eng.state.zones["zone_a"].moisture_pct
    start(eng)
    run(eng, 90)
    assert eng.true_tank_pct < tank0
    assert eng.state.zones["zone_a"].moisture_pct > moist0


def test_booster_holds_setpoint_until_capacity_exceeded(eng):
    start(eng, "zone_a")
    eng.process_commands([cmd("start_zone", "zone_b", "c2")])
    run(eng, 40)
    assert eng.state.system.main_pressure_bar == pytest.approx(3.0, abs=0.05)
    flow_ok = eng.state.system.main_flow_m3h
    fault(eng, "system", "mainline_leak")
    run(eng, 5)  # before leak protection trips
    assert eng.state.system.main_pressure_bar < 2.95  # demand beyond the full-speed curve
    assert eng.state.system.main_flow_m3h > flow_ok


def test_low_tank_sends_direct_well_zone_to_well(eng):
    fault(eng, "tank", "set_level", value=20)
    start(eng, "zone_w")
    run(eng, 30)
    z = eng.state.zones["zone_w"]
    assert z.source_mode == "well_direct" and z.state == "running"
    assert eng.state.pumps["pump_well_01"].state == "running"


def test_well_refills_tank(eng):
    fault(eng, "tank", "set_level", value=50)
    run(eng, 600)
    assert eng.true_tank_pct > 50
    assert eng.state.system.refilling


def test_stop_all(eng):
    start(eng, "zone_a")
    eng.process_commands([cmd("start_zone", "zone_b", "c2")])
    run(eng, 30)
    eng.process_commands([cmd("stop_all")])
    run(eng, 10)
    assert {eng.state.zones[z].state for z in ("zone_a", "zone_b")} == {"completed"}


# ── Faults & protection ──────────────────────────────────


def codes(e):
    return {a.code for a in e.state.alarms.values()}


def test_pump_trip_stops_zone_and_raises_alarm(eng):
    start(eng)
    run(eng, 30)
    fault(eng, "pump", "trip", "pump_booster_01")
    run(eng, 10)
    assert "ALM-005" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"
    assert eng.state.system.main_flow_m3h == pytest.approx(0, abs=0.05)
    # PLC refuses a new start while the pump is tripped
    assert start(eng, "zone_b")["status"] == "failed"
    fault(eng, "pump", "clear", "pump_booster_01")
    run(eng, 1)
    assert "ALM-005" not in codes(eng)


def test_booster_failed_start(eng):
    fault(eng, "pump", "fail_start", "pump_booster_01")
    start(eng)
    run(eng, 15)
    assert "ALM-006" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"
    assert eng.drain_outbox()[0]["status"] == "failed"


def test_valve_stuck_closed_raises_failed_to_open(eng):
    fault(eng, "valve", "stuck_closed", "valve_a")
    start(eng)
    run(eng, 25)
    assert "ALM-019" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"
    assert eng.state.zones["zone_a"].flow_m3h == 0


def test_blocked_line_raises_no_flow(eng):
    fault(eng, "zone", "blocked", "zone_a")
    start(eng)
    run(eng, 30)
    assert "ALM-012" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"


def test_valve_stuck_open_isolated_by_stopping_pump(eng):
    start(eng)
    run(eng, 30)
    fault(eng, "valve", "stuck_open", "valve_a")
    eng.process_commands([cmd("stop_zone", "zone_a", "c2")])
    run(eng, 20)
    assert "ALM-020" in codes(eng)
    assert eng.state.pumps["pump_booster_01"].state == "stopped"
    fault(eng, "valve", "clear", "valve_a")
    run(eng, 10)
    assert "ALM-020" not in codes(eng)
    assert eng.state.valves["valve_a"].status == "closed"


def test_mainline_leak_detected(eng):
    start(eng)
    run(eng, 30)
    fault(eng, "system", "mainline_leak")
    run(eng, 20)
    assert "ALM-013" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"


def test_tank_critical_stops_tank_zones(eng):
    start(eng)
    run(eng, 30)
    fault(eng, "tank", "set_level", value=8)
    run(eng, 10)
    assert "ALM-002" in codes(eng)
    assert eng.state.zones["zone_a"].state == "faulted"


def test_estop_stops_everything_and_blocks_starts(eng):
    start(eng)
    run(eng, 30)
    fault(eng, "system", "estop")
    run(eng, 10)
    assert "ALM-041" in codes(eng)
    assert eng.state.pumps["pump_booster_01"].state == "stopped"
    assert start(eng, "zone_b")["status"] == "failed"
    fault(eng, "system", "estop_release")
    run(eng, 1)
    assert "ALM-041" not in codes(eng)


def test_tank_sensor_fault_freezes_reading(eng):
    start(eng)
    run(eng, 10)
    fault(eng, "sensor", "tank_level_fault", "sensor_tank_level")
    frozen = eng.state.system.tank_level_pct
    run(eng, 120)
    assert eng.state.system.tank_level_pct == frozen
    assert eng.true_tank_pct < frozen
    assert "ALM-003" in codes(eng)
    assert eng.state.sensors["sensor_tank_level"].quality == "bad"


def test_unknown_fault_rejected(eng):
    [res] = eng.process_commands(
        [cmd("inject_fault", None, target_type="pump", target_id="x", fault_type="trip")]
    )
    assert res["status"] == "failed"


def test_deterministic_with_same_seed():
    def run_once():
        e = SimulatorEngine(FarmSimulationState(), seed=7)
        apply_layout(e, ZONES, PUMPS, VALVES, SENSORS)
        start(e)
        run(e, 60)
        return e.state.sensors["sensor_moisture_a"].value, e.state.system.main_pressure_bar

    assert run_once() == run_once()


def test_sync_payloads_include_plc_alarms(eng):
    fault(eng, "system", "estop")
    run(eng, 1)
    payloads = {p["device_key"]: p["state_json"] for p in eng.state.get_sync_payloads()}
    assert payloads["plc_alarms"]["active"][0]["code"] == "ALM-041"
    assert {
        "zone_zone_a",
        "pump_pump_booster_01",
        "valve_valve_a",
        "sensor_sensor_tank_level",
    } <= payloads.keys()


def test_leak_detected_on_large_zone():
    """Regression: a leak on a big zone (Olives, 5–18 m³/h) hid inside a max-flow band."""
    e = SimulatorEngine(FarmSimulationState(), seed=3)
    big = {"id": "zone_big", "code": "BIG", "flow_min_m3h": 5.0, "flow_max_m3h": 18.0}
    apply_layout(e, [big], PUMPS, [{"id": "valve_big", "zone_id": "zone_big"}], [])
    e.process_commands([cmd("start_zone", "zone_big")])
    run(e, 30)
    assert e.state.zones["zone_big"].state == "running"
    fault(e, "system", "mainline_leak")
    run(e, 20)
    assert "ALM-013" in codes(e)


def test_no_false_leak_alarm_on_normal_runs(eng):
    for zid in ("zone_a", "zone_b"):
        eng.process_commands([cmd("start_zone", zid, f"c-{zid}")])
    run(eng, 120)
    assert "ALM-013" not in codes(eng)


def test_stop_during_start_fails_the_start_command(eng):
    start(eng)
    run(eng, 1)  # still starting the pump
    eng.process_commands([cmd("stop_zone", "zone_a", "c2")])
    [update] = eng.drain_outbox()
    assert update["command_id"] == "c1" and update["status"] == "failed"


# ── Virtual clock & simulation time tests ─────────────────


def test_paused_means_no_physics(eng):
    eng.paused = True
    initial_moisture = eng.state.zones["zone_a"].moisture_pct
    initial_tank = eng.state.system.tank_level_pct
    initial_sim_time = eng.sim_time

    # Run steps while paused
    eng.step(10.0)
    eng.step(10.0)

    assert eng.sim_time == initial_sim_time
    assert eng.state.zones["zone_a"].moisture_pct == initial_moisture
    assert eng.state.system.tank_level_pct == initial_tank


def test_timescale_physics_acceleration(eng):
    # Running 600 simulated seconds (e.g. 10 real seconds at 60x)
    initial_moisture = eng.state.zones["zone_a"].moisture_pct
    run(eng, 600.0, dt=1.0)
    # Moisture should dry over 600 simulated seconds
    assert eng.state.zones["zone_a"].moisture_pct < initial_moisture


def test_jump_stops_running_zones_and_approximates(eng):
    from datetime import timedelta

    start(eng)
    run(eng, 40)
    assert eng.state.zones["zone_a"].state == "running"

    t_jump = eng.sim_time + timedelta(hours=4)
    eng.jump(t_jump)

    assert eng.sim_time == t_jump
    assert eng.state.zones["zone_a"].state == "off"
    assert eng.state.zones["zone_a"].health == "healthy"
    assert eng.state.zones["zone_a"].flow_m3h == 0.0
    assert eng.state.pumps["pump_booster_01"].state == "stopped"


def test_pumps_restart_after_forward_and_backward_jump(eng):
    from datetime import timedelta

    # 1. Start zone and get it to running
    assert start(eng)["status"] == "accepted"
    run(eng, 40)
    assert eng.state.zones["zone_a"].state == "running"
    assert eng.state.pumps["pump_booster_01"].state == "running"

    # 2. Forward jump
    t_forward = eng.sim_time + timedelta(hours=4)
    eng.jump(t_forward)
    assert eng.state.zones["zone_a"].state == "off"
    assert eng.state.pumps["pump_booster_01"].state == "stopped"

    # 3. Start zone after forward jump -> must reach running with pump running
    res_fwd = start(eng)
    assert res_fwd["status"] == "accepted"
    run(eng, 40)
    assert eng.state.zones["zone_a"].state == "running"
    assert eng.state.pumps["pump_booster_01"].state == "running"

    # 4. Backward jump / reset (e.g. Back to real time)
    t_back = eng.sim_time - timedelta(hours=2)
    eng.jump(t_back)
    assert eng.state.zones["zone_a"].state == "off"
    assert eng.state.pumps["pump_booster_01"].state == "stopped"

    # 5. Start zone after backward jump -> must reach running with pump running
    res_back = start(eng)
    assert res_back["status"] == "accepted"
    run(eng, 40)
    assert eng.state.zones["zone_a"].state == "running"
    assert eng.state.pumps["pump_booster_01"].state == "running"


def test_manual_step_advances_physics_while_paused_without_killing_zones(eng):
    start(eng)
    run(eng, 40)
    assert eng.state.zones["zone_a"].state == "running"
    initial_runtime = eng.state.zones["zone_a"].runtime_sec

    # Pause the simulator
    eng.paused = True
    assert eng.paused is True

    # Regular step while paused: does nothing
    eng.step(10.0)
    assert eng.state.zones["zone_a"].runtime_sec == initial_runtime

    # Manual step: advances physics for 60 seconds without killing the zone
    eng.manual_step(60.0)
    assert eng.paused is True  # still paused after step
    assert eng.state.zones["zone_a"].state == "running"  # NOT killed!
    assert eng.state.zones["zone_a"].runtime_sec == initial_runtime + 60.0
    assert eng.state.zones["zone_a"].flow_m3h > 0.0
