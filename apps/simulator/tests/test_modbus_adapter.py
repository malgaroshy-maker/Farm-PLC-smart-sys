"""Modbus TCP adapter (G7/G5) against an in-process Modbus server playing the farm PLC."""

import asyncio
import json
from pathlib import Path

from src.adapter import Layout
from src.adapters import plc_common as pc
from src.adapters.modbus_adapter import ModbusAdapter, load_map
from src.modbus_tcp import ModbusTcpClient, ModbusTcpServer

EXAMPLE = Path(__file__).resolve().parents[1] / "modbus_map.example.json"


def _regmap(port: int) -> dict:
    m = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    m["host"], m["port"] = "127.0.0.1", port
    return m


def _plc(server: ModbusTcpServer, regmap: dict, silent: bool = False):
    """Answers the handshake like the PLC: zone index 2 is interlocked (zone in manual)."""
    c = {k: v["hr"] for k, v in regmap["command"].items()}

    def on_write(addr, _vals):
        if addr != c["seq"] or silent:
            return
        r = server.regs
        ok = not (r[c["type"]] == 1 and r[c["target"]] == 2)
        r[c["ack_status"]] = 1 if ok else 2
        r[c["ack_reason"]] = 0 if ok else 2
        r[c["ack_seq"]] = r[c["seq"]]

    server.on_write = on_write


def run(coro):
    asyncio.run(coro)


def test_client_round_trip():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        client = ModbusTcpClient("127.0.0.1", port)
        try:
            await client.write_register(10, 1234)
            await client.write_registers(20, [1, 2, 0xFFFF])
            assert await client.read_holding(10, 1) == [1234]
            assert await client.read_holding(20, 3) == [1, 2, 0xFFFF]
        finally:
            await client.close()
            await server.stop()

    run(go())


def test_reads_state_with_scaling_states_and_alarms():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        regmap = _regmap(port)
        r = server.regs
        r[0], r[2], r[4], r[5], r[7] = (
            1,
            1,
            725,
            240,
            1830,
        )  # auto, power ok, 72.5 %, 2.4 bar, 18.3 m
        r[100], r[101], r[102], r[104], r[105] = 1, 1, 310, 312, 1  # zone 1 waters, panel 'on'
        r[106], r[107], r[108] = 4 + 256 * 1, 725, 0  # running, started by the panel, 725 s
        r[116], r[119] = 7, 12  # zone 2 faulted with ALM-012 (no flow)
        r[270], r[274], r[276], r[283] = 1, 375, 42, 2  # booster 3.75 kW, 4.2 kWh; well 'off'
        r[10] = (1 << (5 - 1)) | (1 << (2 - 1))  # ALM-005 booster trip, ALM-002 tank critical
        r[12] = 1 << (41 - 33)  # ALM-041 E-stop
        adapter = ModbusAdapter(regmap)
        try:
            await adapter.start(Layout(zones=[{"id": "zone_rumman_1"}]))
            st = {p["device_key"]: p["state_json"] for p in await adapter.read_state()}
            assert st["simulation_stats"]["tank_level_pct"] == 72.5
            assert st["simulation_stats"]["well_level_m"] == 18.3
            assert st["system_mode"]["mode"] == "auto" and st["system_mode"]["power_ok"]
            z = st["zone_zone_rumman_1"]
            assert z["state"] == "running" and z["run_source"] == "panel"
            assert z["flow_m3h"] == 3.1 and z["moisture_pct"] == 31.2 and z["runtime_sec"] == 725
            assert z["panel_mode"] == "on"
            assert st["valve_valve_rumman_1"]["status"] == "open"
            assert st["valve_valve_rumman_1"]["last_command"] == "open"  # the app requires it
            assert st["zone_zone_rumman_2"]["state"] == "faulted"
            assert st["zone_zone_rumman_3"]["state"] == "off"
            assert st["pump_pump_booster_01"]["state"] == "running"
            assert st["pump_pump_booster_01"]["power_kw"] == 3.75
            assert st["pump_pump_booster_01"]["energy_kwh_today"] == 4.2
            assert st["pump_pump_well_01"]["panel_mode"] == "off"
            alarms = {(a["code"], a["zone_id"], a["device_id"]) for a in st["plc_alarms"]["active"]}
            assert alarms == {
                ("ALM-002", None, None),
                ("ALM-005", None, "pump_booster_01"),
                ("ALM-041", None, None),
                ("ALM-012", "zone_rumman_2", None),
            }
        finally:
            await adapter.stop()
            await server.stop()

    run(go())


def test_command_handshake_accept_reject_and_unknown():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        regmap = _regmap(port)
        _plc(server, regmap)
        adapter = ModbusAdapter(regmap, ack_timeout_s=2)
        try:
            await adapter.start(Layout())
            res = await adapter.execute(
                [
                    {
                        "id": "c1",
                        "command_type": "start_zone",
                        "target_id": "zone_rumman_1",
                        "payload": {"duration_min": 25},
                    },
                    {
                        "id": "c2",
                        "command_type": "start_zone",
                        "target_id": "zone_rumman_2",
                        "payload": '{"duration_min": 10}',
                    },
                    {"id": "c3", "command_type": "start_zone", "target_id": "zone_nowhere"},
                    {"id": "c4", "command_type": "set_panel", "target_id": "zone_rumman_1"},
                    {"id": "c5", "command_type": "stop_all"},
                ]
            )
            by = {x["command_id"]: x for x in res}
            assert by["c1"]["status"] == "completed"
            assert by["c2"] == {
                "command_id": "c2",
                "status": "failed",
                "failure_reason": "zone_in_manual",
            }
            assert by["c3"]["failure_reason"] == "no_registers_for:zone_nowhere"
            assert by["c4"]["failure_reason"].startswith("unsupported_command")
            assert by["c5"]["status"] == "completed"
            assert server.regs[303] == 0 and server.regs[300] == 3  # stop_all last, 3 handshakes
        finally:
            await adapter.stop()
            await server.stop()

    run(go())


def test_heartbeat_only_after_the_api_took_a_push():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        adapter = ModbusAdapter(_regmap(port))
        try:
            await adapter.start(Layout())
            await adapter.read_state()
            assert server.regs[307] == 0  # gateway alive but the API never answered
            adapter.api_contact()
            await adapter.read_state()
            await adapter.read_state()
            assert server.regs[307] == 1  # one contact -> one beat
            adapter.api_contact()
            await adapter.read_state()
            assert server.regs[307] == 2
        finally:
            await adapter.stop()
            await server.stop()

    run(go())


def test_fallback_program_is_written_then_committed():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        adapter = ModbusAdapter(_regmap(port))
        writes = []
        server.on_write = lambda addr, vals: writes.append(addr)
        runs = [
            # Tuesday 2026-11-24 06:00, 30 min on zone_rumman_1 (index 1)
            {
                "zone_id": "zone_rumman_1",
                "scheduled_start_farm": "2026-11-24T06:00:00",
                "duration_min": 30,
            },
            {
                "zone_id": "zone_unknown",
                "scheduled_start_farm": "2026-11-24T07:00:00",
                "duration_min": 10,
            },
            # Sunday 2026-11-29 22:15, 45 min on zone_fruit_mix (index 12)
            {
                "zone_id": "zone_fruit_mix",
                "scheduled_start_farm": "2026-11-29T22:15:00",
                "duration_min": 45,
            },
        ]
        try:
            await adapter.start(Layout())
            await adapter.load_fallback(runs)
            r = server.regs
            assert r[320:328] == [1, 360, 30, 3, 12, 1335, 45, 1]  # weekday: Sun=1, Tue=3
            assert r[319] == 2 and r[318] == 1
            assert writes[-1] == 318  # the commit comes last
        finally:
            await adapter.stop()
            await server.stop()

    run(go())


def test_no_ack_and_lost_link():
    async def go():
        server = ModbusTcpServer()
        port = await server.start()
        regmap = _regmap(port)
        _plc(server, regmap, silent=True)
        adapter = ModbusAdapter(regmap, ack_timeout_s=0.3)
        try:
            await adapter.start(Layout())
            res = await adapter.execute([{"id": "c1", "command_type": "stop_all"}])
            assert res[0]["failure_reason"] == "plc_no_ack"
            await server.stop()
            await adapter.client.close()
            assert await adapter.read_state() == []
            assert not adapter.link_ok()
        finally:
            await adapter.stop()

    run(go())


def test_plc_common_helpers():
    assert pc.alarm_bits([0b101, 0, 1]) == {1, 3, 33}
    assert pc.zone_state(8) == "interrupted" and pc.zone_state(99) == "off"
    assert pc.plc_alarms({8, 33}, {"z1": 33, "z2": 10}) == [
        {"code": "ALM-033", "device_id": None, "zone_id": None},
        {"code": "ALM-033", "device_id": None, "zone_id": "z1"},
    ]  # ALM-008 / ALM-010 are the app's own (derived) alarms


def test_load_map_validates(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"host": "x"}), encoding="utf-8")
    try:
        load_map(p)
    except ValueError as exc:
        assert "system" in str(exc)
    else:
        raise AssertionError("expected a MapError")
    assert load_map(EXAMPLE)["port"] == 502
