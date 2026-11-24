"""G5: the production Modbus adapter against the virtual farm PLC (simulator behind registers)."""

import asyncio
import json
from pathlib import Path

from src.adapter import Layout
from src.client import apply_layout
from src.engine import SimulatorEngine
from src.state import FarmSimulationState
from src.virtual_plc import VirtualPlantGateway, VirtualPlc, reason_code
from tests.test_engine import PUMPS, SENSORS, VALVES, ZONES, run

EXAMPLE = Path(__file__).resolve().parents[1] / "modbus_map.example.json"


def _setup():
    e = SimulatorEngine(FarmSimulationState(), seed=1)
    apply_layout(e, ZONES, PUMPS, VALVES, SENSORS)
    e.state.system.tank_level_pct = e.true_tank_pct = 80.0
    m = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    template = next(iter(m["zones"].values()))
    zones = {}
    for i, z in enumerate(ZONES, 1):  # the test farm's zones at PLC indexes 1..3
        b = 100 + 10 * (i - 1)
        zones[z["id"]] = {
            k: (
                {"hr": b + (spec["hr"] - 100)}
                | ({"scale": spec["scale"]} if "scale" in spec else {})
            )
            if isinstance(spec, dict)
            else i
            for k, spec in template.items()
        }
    m["zones"] = zones
    return e, m


async def _wire(e, m):
    plc = VirtualPlc(e, m)
    port = await plc.start("127.0.0.1", 0)
    m["host"], m["port"] = "127.0.0.1", port
    gw = VirtualPlantGateway(m, e, ack_timeout_s=2)
    await gw.start(Layout())
    loop = asyncio.create_task(plc.run_loop(0.02))
    return plc, gw, loop


async def _close(plc, gw, loop):
    plc.running = False
    loop.cancel()
    await gw.stop()
    await plc.stop()


def test_reason_codes():
    assert reason_code("Zone A is switched to ON on the panel") == 2
    assert reason_code("No mains power") == 3
    assert reason_code("Booster pump unavailable") == 4
    assert reason_code("something else") == 9


def test_start_runs_the_zone_through_the_plc_path():
    async def go():
        e, m = _setup()
        plc, gw, loop = await _wire(e, m)
        try:
            res = await gw.execute(
                [
                    {
                        "id": "c1",
                        "command_type": "start_zone",
                        "target_id": "zone_a",
                        "payload": {"duration_min": 5},
                    }
                ]
            )
            assert res == [{"command_id": "c1", "status": "completed"}]
            run(e, 60)
            plc.sync()
            st = {p["device_key"]: p["state_json"] for p in await gw.read_state()}
            z = st["zone_zone_a"]
            assert z["state"] == "running" and z["run_source"] == "app"
            assert z["flow_m3h"] > 0 and z["target_runtime_sec"] == 300
            assert z["runtime_sec"] == round(
                e.state.zones["zone_a"].runtime_sec
            )  # seconds, not minutes
            assert st["pump_pump_booster_01"]["state"] == "running"
            assert "sensor_sensor_moisture_a" in st  # field sensors still reach the app
        finally:
            await _close(plc, gw, loop)

    asyncio.run(go())


def test_panel_switch_is_a_plant_input_and_the_plc_refuses_the_app():
    async def go():
        e, m = _setup()
        plc, gw, loop = await _wire(e, m)
        try:
            res = await gw.execute(
                [
                    {
                        "id": "p1",
                        "command_type": "set_panel",
                        "target_id": "zone_b",
                        "payload": {"kind": "zone", "position": "on"},
                    }
                ]
            )
            assert res[0]["status"] == "completed"  # straight to the simulated farm
            res = await gw.execute(
                [
                    {"id": "c2", "command_type": "stop_zone", "target_id": "zone_b"},
                    {
                        "id": "c3",
                        "command_type": "start_zone",
                        "target_id": "zone_b",
                        "payload": {"duration_min": 5},
                    },
                ]
            )
            assert [r.get("failure_reason") for r in res] == ["zone_in_manual", "zone_in_manual"]
            run(e, 30)
            plc.sync()
            st = {p["device_key"]: p["state_json"] for p in await gw.read_state()}
            assert st["zone_zone_b"]["panel_mode"] == "on"
            assert st["zone_zone_b"]["run_source"] == "panel"
        finally:
            await _close(plc, gw, loop)

    asyncio.run(go())


def test_heartbeat_and_fallback_list_reach_the_plc():
    async def go():
        e, m = _setup()
        plc, gw, loop = await _wire(e, m)
        try:
            seen = e.api_seen
            gw.api_contact()
            await gw.read_state()
            await asyncio.sleep(0.1)
            assert e.api_seen > seen  # heartbeat -> the PLC knows the app is alive
            start = e.sim_time.replace(second=0, microsecond=0)
            await gw.load_fallback(
                [
                    {
                        "zone_id": "zone_a",
                        "scheduled_start_farm": start.replace(tzinfo=None).isoformat(),
                        "duration_min": 20,
                    }
                ]
            )
            await asyncio.sleep(0.1)
            assert len(e.fallback) == 1 and e.fallback[0]["zone_id"] == "zone_a"
            assert e.fallback[0]["start"].hour == start.hour and e.fallback[0]["duration_min"] == 20
        finally:
            await _close(plc, gw, loop)

    asyncio.run(go())


def test_pump_trip_becomes_a_plc_alarm_on_the_pump():
    async def go():
        e, m = _setup()
        plc, gw, loop = await _wire(e, m)
        try:
            await gw.execute(
                [
                    {
                        "id": "c1",
                        "command_type": "start_zone",
                        "target_id": "zone_a",
                        "payload": {"duration_min": 5},
                    }
                ]
            )
            run(e, 60)
            await gw.execute(
                [
                    {
                        "id": "f1",
                        "command_type": "inject_fault",
                        "payload": {
                            "target_type": "pump",
                            "target_id": "pump_booster_01",
                            "fault_type": "trip",
                        },
                    }
                ]
            )
            run(e, 5)
            plc.sync()
            st = {p["device_key"]: p["state_json"] for p in await gw.read_state()}
            codes = {(a["code"], a["device_id"]) for a in st["plc_alarms"]["active"]}
            assert ("ALM-005", "pump_booster_01") in codes
            assert st["pump_pump_booster_01"]["state"] == "faulted"
        finally:
            await _close(plc, gw, loop)

    asyncio.run(go())


def test_comms_drop_cuts_the_plc_link():
    async def go():
        e, m = _setup()
        plc, gw, loop = await _wire(e, m)
        try:
            assert gw.link_ok()
            e.faults.handle({"target_type": "comms", "fault_type": "drop", "value": 30})
            assert not gw.link_ok()  # the gateway stops pushing -> the app sees stale data
        finally:
            await _close(plc, gw, loop)

    asyncio.run(go())
