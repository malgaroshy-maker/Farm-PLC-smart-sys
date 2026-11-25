"""G5: the farm model that plays the field around the real PLC in PLCSIM (no PLCSIM needed here)."""

from src.plcsim_plant import RAW_FULL, Plant


def plant() -> Plant:
    return Plant(zone_index={"zone_rumman_1": 1, "zone_enab": 11})


def run(p: Plant, seconds: float, lo=0, hi=0, booster=False, well=False):
    for _ in range(int(seconds / 0.2)):
        p.step(0.2, lo, hi, booster, well)


def inputs(p: Plant) -> dict[str, str]:
    return {op.split()[1]: op.split()[3] for op in p.inputs()}


def test_pump_feedback_follows_the_start_after_a_delay_and_water_flows():
    p = plant()
    run(p, 1.0, lo=0b1, booster=True)
    assert not p.booster_run  # contactor + motor take 1.5 s
    run(p, 1.0, lo=0b1, booster=True)
    assert p.booster_run and p.main_flow == 4.0 and p.main_pressure > 2.0
    i = inputs(p)
    assert i["DI_BoosterRun"] == "1"
    assert int(i["AI_MainFlow"]) == int(4.0 / 50.0 * RAW_FULL)


def test_zone_bits_map_to_the_plc_valve_bytes():
    p = plant()
    run(p, 3.0, hi=0b100, booster=True)  # zone 11 = bit 2 of the high byte
    assert p.main_flow == 4.0
    run(p, 1.0, booster=True)  # valve closed: dead-headed pump
    assert p.main_flow == 0.0 and p.main_pressure == 3.8


def test_faults_reach_the_plc_inputs():
    p = plant()
    assert p.apply("inject_fault", None, {"target_type": "system", "fault_type": "estop"}) == (
        True,
        None,
    )
    assert p.apply(
        "inject_fault",
        None,
        {"target_type": "pump", "target_id": "pump_booster_01", "fault_type": "trip"},
    )[0]
    p.apply("set_panel", "zone_enab", {"kind": "zone", "position": "on"})
    p.apply("set_panel", "pump_well_01", {"kind": "pump", "position": "off"})
    i = inputs(p)
    assert i["DI_EStopOk"] == "0" and i["DI_BoosterFault"] == "1"
    assert i["DI_ZoneOnHi"] == str(0b100) and i["DI_WellOff"] == "1"
    run(p, 3.0, lo=0b1, booster=True)
    assert not p.booster_run  # a tripped pump never runs
    p.apply("inject_fault", None, {"target_type": "system", "fault_type": "clear_all"})
    i = inputs(p)
    assert i["DI_EStopOk"] == "1" and i["DI_BoosterFault"] == "0" and i["DI_ZoneOnHi"] == "0"


def test_stuck_and_hand_opened_valves():
    p = plant()
    p.apply(
        "inject_fault",
        None,
        {"target_type": "valve", "target_id": "valve_rumman_1", "fault_type": "stuck_closed"},
    )
    run(p, 3.0, lo=0b1, booster=True)
    assert p.main_flow == 0.0  # the PLC opened it, no water: it will fault the zone (ALM-012)
    p.apply(
        "inject_fault",
        None,
        {"target_type": "valve", "target_id": "valve_rumman_1", "fault_type": "hand_open"},
    )
    run(p, 1.0, booster=True)
    assert p.main_flow == 4.0  # water with no valve command: the PLC raises ALM-021


def test_tank_well_and_power():
    p = plant()
    p.tank_pct = 50.0
    run(p, 60.0, well=True)
    assert p.tank_pct > 50.0 and p.well_m < 12.0  # refilling draws the well down
    p.apply("inject_fault", None, {"target_type": "system", "fault_type": "power_cut"})
    run(p, 1.0, well=True)
    assert not p.well_run and inputs(p)["DI_MainsOk"] == "0"
    p.apply("inject_fault", None, {"target_type": "system", "fault_type": "well_low"})
    run(p, 200.0)
    assert p.well_m < 1.5  # below the PLC's dry-run level
    assert (
        p.apply("inject_fault", None, {"target_type": "system", "fault_type": "nope"})[0] is False
    )
