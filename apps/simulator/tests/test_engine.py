"""Simulator engine state-machine tests (no API needed)."""

import asyncio

from src.engine import SimulatorEngine
from src.state import FarmSimulationState, SimPumpState, SimZoneState, utcnow


def make_engine() -> SimulatorEngine:
    state = FarmSimulationState()
    now = utcnow()
    for zid in ("zone_a", "zone_b"):
        state.zones[zid] = SimZoneState(zone_id=zid, last_updated=now)
    state.pumps["pump_1"] = SimPumpState(pump_id="pump_1", last_updated=now)
    return SimulatorEngine(state)


def run_ticks(engine: SimulatorEngine, n: int) -> None:
    for _ in range(n):
        asyncio.run(engine.tick(1.0))


def cmd(ctype: str, target: str | None = None) -> dict:
    return {"id": f"c-{ctype}", "command_type": ctype, "target_id": target}


def test_start_zone_reaches_running_and_starts_pump():
    e = make_engine()
    [res] = e.process_commands([cmd("start_zone", "zone_a")])
    assert res["status"] == "completed"
    run_ticks(e, 3)
    assert e.state.zones["zone_a"].state == "running"
    assert e.state.pumps["pump_1"].state == "running"
    assert e.state.system.main_flow_m3h > 0


def test_stop_zone_stops_pump_when_last_zone():
    e = make_engine()
    e.process_commands([cmd("start_zone", "zone_a")])
    run_ticks(e, 3)
    e.process_commands([cmd("stop_zone", "zone_a")])
    run_ticks(e, 1)
    assert e.state.zones["zone_a"].state == "completed"
    assert e.state.pumps["pump_1"].state == "stopped"


def test_stop_all_stops_every_active_zone():
    e = make_engine()
    e.process_commands([cmd("start_zone", "zone_a"), cmd("start_zone", "zone_b")])
    run_ticks(e, 3)
    e.process_commands([cmd("stop_all")])
    run_ticks(e, 1)
    assert {z.state for z in e.state.zones.values()} == {"completed"}


def test_unknown_zone_fails():
    e = make_engine()
    [res] = e.process_commands([cmd("start_zone", "zone_x")])
    assert res["status"] == "failed"


def test_sync_payloads_are_json_ready():
    e = make_engine()
    keys = {p["device_key"] for p in e.state.get_sync_payloads()}
    assert {"system_mode", "simulation_stats", "zone_zone_a", "pump_pump_1"} <= keys
