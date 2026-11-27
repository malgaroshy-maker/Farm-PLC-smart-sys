"""G7 field readiness: panel switches, power-cut resume rule, hand-opened valve, fallback program."""

from datetime import timedelta

import pytest

from src import engine as engine_mod
from src.client import apply_layout
from src.engine import SimulatorEngine
from src.state import FarmSimulationState, utcnow
from tests.test_engine import PUMPS, SENSORS, VALVES, ZONES, cmd, fault, run


@pytest.fixture()
def eng() -> SimulatorEngine:
    e = SimulatorEngine(FarmSimulationState(), seed=1)
    apply_layout(e, ZONES, PUMPS, VALVES, SENSORS)
    e.state.system.tank_level_pct = e.true_tank_pct = 80.0
    return e


def panel(e, kind, target, position):
    return e.process_commands([cmd("set_panel", target, kind=kind, position=position)])[0]


def test_zone_switch_on_runs_the_zone_without_the_app(eng):
    assert panel(eng, "zone", "zone_a", "on")["status"] == "completed"
    run(eng, 20)
    z = eng.state.zones["zone_a"]
    assert z.state == "running" and z.run_source == "panel"
    assert eng.state.pump_of_type("booster").state == "running"
    assert z.flow_m3h > 0
    # back to Auto: the zone stops on its own
    panel(eng, "zone", "zone_a", "auto")
    run(eng, 15)
    assert z.state == "completed" and z.run_source is None


def test_zone_switch_off_blocks_app_starts(eng):
    panel(eng, "zone", "zone_a", "off")
    res = eng.process_commands([cmd("start_zone", "zone_a", duration_min=2)])[0]
    assert res["status"] == "failed" and "panel" in res["failure_reason"]


def test_pump_switch_off_blocks_and_hand_runs(eng):
    panel(eng, "pump", "pump_booster_01", "off")
    res = eng.process_commands([cmd("start_zone", "zone_a", duration_min=2)])[0]
    assert res["status"] == "failed" and "OFF" in res["failure_reason"]
    panel(eng, "pump", "pump_booster_01", "hand")
    run(eng, 6)
    assert eng.state.pump_of_type("booster").state == "running"


@pytest.mark.parametrize("outage_min, resumed", [(10, True), (45, False)])
def test_power_cut_resume_rule(eng, outage_min, resumed):
    eng.process_commands([cmd("start_zone", "zone_a", duration_min=2)])
    run(eng, 30)
    z = eng.state.zones["zone_a"]
    assert z.state == "running"
    fault(eng, "system", "power_cut")
    run(eng, 2)
    assert z.state == "interrupted" and not eng.state.system.power_ok
    assert "ALM-033:system" in eng.state.alarms
    eng.sim_time += timedelta(minutes=outage_min)
    fault(eng, "system", "power_restore")
    run(eng, 2)
    assert eng.state.system.power_ok and "ALM-033:system" not in eng.state.alarms
    if resumed:
        assert z.state in ("starting_pump", "opening_valve", "validating_flow", "running")
        assert z.run_source == "resume"
    else:
        assert z.state == "faulted"
        assert "ALM-033:zone_a" in eng.state.alarms


def test_valve_opened_by_hand_shows_open_feedback(eng):
    fault(eng, "valve", "hand_open", "valve_b")
    run(eng, 2)
    assert eng.state.valves["valve_b"].status == "open"
    assert eng.state.zones["zone_b"].state == "off"


def test_fallback_program_runs_when_the_app_is_gone(eng, monkeypatch):
    start = eng.sim_time - timedelta(minutes=1)
    eng.load_fallback(
        [
            {
                "program_id": "p1",
                "step_order": 1,
                "zone_id": "zone_b",
                "scheduled_start_farm": start.isoformat(),
                "duration_min": 10,
            }
        ]
    )
    run(eng, 2)
    assert eng.state.zones["zone_b"].state == "off"  # app still there: nothing happens
    monkeypatch.setattr(engine_mod, "FALLBACK_AFTER_S", 0.0)
    eng.api_seen = utcnow() - timedelta(seconds=5)
    run(eng, 2)
    z = eng.state.zones["zone_b"]
    assert eng.state.system.fallback_active
    assert z.state != "off" and z.run_source == "fallback"
    assert 8 * 60 <= z.target_runtime_sec <= 9 * 60  # only the time left in the slot
    run(eng, 4)
    assert len(eng.fallback_done) == 1  # never started twice


def test_pump_health_energy_and_well_dry_run(eng):
    eng.process_commands([cmd("start_zone", "zone_a", duration_min=2)])
    run(eng, 60)
    booster = eng.state.pump_of_type("booster")
    assert booster.power_kw > 0 and booster.current_a > 0 and booster.energy_kwh_today > 0
    # aquifer drawn down while the well refills the tank → PLC stops the well pump
    eng.state.system.tank_level_pct = eng.true_tank_pct = 40.0
    eng.state.system.well_level_m = 1.6
    fault(eng, "system", "well_low")
    run(eng, 400)
    assert "ALM-027:system" in eng.state.alarms
    assert eng.state.pump_of_type("well").state != "running"


def test_filter_clog_and_clean(eng):
    fault(eng, "system", "filter_clog")
    assert eng.state.system.filter_dp_bar > 0.5
    fault(eng, "system", "filter_clean")
    assert eng.state.system.filter_dp_bar < 0.1


@pytest.mark.parametrize("stop", ["stop_all", "stop_zone"])
def test_a_stop_during_a_power_cut_cancels_the_resume(eng, stop):
    """Safety: a zone that was stopped must not start again by itself when power returns."""
    eng.process_commands([cmd("start_zone", "zone_a", duration_min=10)])
    run(eng, 30)
    fault(eng, "system", "power_cut")
    run(eng, 2)
    z = eng.state.zones["zone_a"]
    assert z.state == "interrupted"
    eng.process_commands([cmd(stop, "zone_a" if stop == "stop_zone" else "")])
    assert z.state == "off"
    fault(eng, "system", "power_restore")
    run(eng, 30)
    assert z.state == "off"
