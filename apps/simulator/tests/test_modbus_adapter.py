"""Milestone G7: the Modbus TCP adapter against an in-process Modbus server playing the PLC."""

import asyncio
import json
from pathlib import Path

from src.adapter import Layout
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


def test_client_round_trip():
    async def run():
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

    asyncio.run(run())


def test_reads_state_with_scaling():
    async def run():
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
        r[100], r[101], r[102], r[104], r[105] = 1, 1, 310, 312, 1  # zone 1 running, panel 'on'
        r[270], r[274], r[283] = 1, 375, 2  # booster runs at 3.75 kW; well pump panel 'off'
        adapter = ModbusAdapter(regmap)
        try:
            await adapter.start(Layout(zones=[{"id": "zone_rumman_1"}]))
            assert adapter.link_ok()
            st = {p["device_key"]: p["state_json"] for p in await adapter.read_state()}
            assert st["simulation_stats"]["tank_level_pct"] == 72.5
            assert st["simulation_stats"]["well_level_m"] == 18.3
            assert st["system_mode"]["mode"] == "auto" and st["system_mode"]["power_ok"]
            z = st["zone_zone_rumman_1"]
            assert z["state"] == "running" and z["flow_m3h"] == 3.1 and z["moisture_pct"] == 31.2
            assert z["panel_mode"] == "on"
            assert st["valve_valve_rumman_1"]["status"] == "open"
            assert st["zone_zone_rumman_2"]["state"] == "idle"
            assert st["pump_pump_booster_01"]["state"] == "running"
            assert st["pump_pump_booster_01"]["power_kw"] == 3.75
            assert st["pump_pump_well_01"]["panel_mode"] == "off"
        finally:
            await adapter.stop()
            await server.stop()

    asyncio.run(run())


def test_command_handshake_accept_reject_and_unknown():
    async def run():
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
            assert by["c2"] == {"command_id": "c2", "status": "failed", "reason": "zone_in_manual"}
            assert by["c3"]["reason"] == "no_registers_for:zone_nowhere"
            assert by["c4"]["reason"].startswith("unsupported_command")
            assert by["c5"]["status"] == "completed"
            assert (
                server.regs[303] == 0 and server.regs[300] == 3
            )  # stop_all sent last, 3 handshakes
        finally:
            await adapter.stop()
            await server.stop()

    asyncio.run(run())


def test_no_ack_and_lost_link():
    async def run():
        server = ModbusTcpServer()
        port = await server.start()
        regmap = _regmap(port)
        _plc(server, regmap, silent=True)
        adapter = ModbusAdapter(regmap, ack_timeout_s=0.3)
        try:
            await adapter.start(Layout())
            res = await adapter.execute([{"id": "c1", "command_type": "stop_all"}])
            assert res[0]["reason"] == "plc_no_ack"
            await server.stop()
            await adapter.client.close()
            assert await adapter.read_state() == []
            assert not adapter.link_ok()
        finally:
            await adapter.stop()

    asyncio.run(run())


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
