"""G5: the OPC UA adapter against a server built from opcua_tagmap.example.json.

Every node of the farm PLC's tag map exists with the PLC's data type (S7 Int = Int16,
DInt = Int32, Word = UInt16), so a wrong type or a missing node fails here before PLCSIM.
"""

import asyncio
import json
import socket
from pathlib import Path

import pytest

asyncua = pytest.importorskip("asyncua")
from asyncua import Server, ua  # noqa: E402

from src.adapter import Layout  # noqa: E402
from src.adapters.opcua_adapter import OpcUaAdapter, TagMapError  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "opcua_tagmap.example.json"
BOOLS = {
    "running",
    "valve_open_fb",
    "estop",
    "power_ok",
    "fallback_active",
    "refilling",
    "run_fb",
    "valid",
}
STRINGS = {"mode", "target", "ack_reason", "config_id"}
WORDS = {"alarm_word0", "alarm_word1", "alarm_word2"}
DINTS = {"runtime_sec", "target_sec"}
REALS = {
    "tank_level_pct",
    "main_pressure_bar",
    "main_flow_m3h",
    "well_level_m",
    "filter_dp_bar",
    "flow_m3h",
    "pressure_bar",
    "moisture_pct",
    "runtime_hours",
    "power_kw",
    "current_a",
    "energy_kwh_today",
}


def vtype(key: str, group: str):
    if key == "fault":
        return ua.VariantType.Boolean if group == "pump" else ua.VariantType.Int16
    if key in BOOLS:
        return ua.VariantType.Boolean
    if key in STRINGS:
        return ua.VariantType.String
    if key in WORDS:
        return ua.VariantType.UInt16
    if key in DINTS:
        return ua.VariantType.Int32
    if key in REALS:
        return ua.VariantType.Float
    return ua.VariantType.Int16


def default(t):
    return {
        ua.VariantType.Boolean: False,
        ua.VariantType.String: "",
        ua.VariantType.Float: 0.0,
    }.get(t, 0)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _entries(tm: dict):
    for k, nid in tm["system"].items():
        yield "system", k, nid
    for z in tm["zones"].values():
        for k, nid in z.items():
            if k != "index":
                yield "zone", k, nid
    for p in tm["pumps"].values():
        for k, nid in p.items():
            yield "pump", k, nid
    for k, nid in tm["command"].items():
        yield "command", k, nid
    yield "fallback", "count", tm["fallback"]["count"]
    yield "fallback", "load_seq", tm["fallback"]["load_seq"]
    for run in tm["fallback"]["runs"]:
        for k, nid in run.items():
            yield "fallback", k, nid


async def _plc(port: int):
    tm = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    tm["endpoint"] = f"opc.tcp://127.0.0.1:{port}"
    server = Server()
    await server.init()
    server.set_endpoint(tm["endpoint"])
    await server.register_namespace("urn:test:filler")
    ns = await server.register_namespace("urn:test:farm-plc")
    assert ns == 3, "the tag map's node ids use ns=3"
    root = await server.nodes.objects.add_object(ns, "PLC")
    nodes = {}
    for group, key, nid in _entries(tm):
        sid = nid.split(";s=", 1)[1]
        t = vtype(key, group)
        node = await root.add_variable(ua.NodeId(sid, ns), sid, ua.Variant(default(t), t))
        await node.set_writable()
        nodes[nid] = (node, t)
    for zid, tags in tm["zones"].items():  # the PLC's DB_Config holds each zone's id
        await nodes[tags["config_id"]][0].write_value(ua.Variant(zid, ua.VariantType.String))
    return server, tm, nodes


async def _set(nodes, nid, value):
    node, t = nodes[nid]
    await node.write_value(ua.Variant(value, t))


async def _get(nodes, nid):
    return await nodes[nid][0].read_value()


def test_farm_plc_tag_map_end_to_end():
    async def run():
        port = _free_port()
        server, tm, nodes = await _plc(port)
        z1 = tm["zones"]["zone_rumman_1"]
        z2 = tm["zones"]["zone_rumman_2"]
        cmd = tm["command"]

        async def plc_logic():
            last = 0
            while True:
                seq = await _get(nodes, cmd["seq"])
                if seq != last:
                    last = seq
                    target = await _get(nodes, cmd["target"])
                    ok = target != "zone_rumman_2"
                    await _set(nodes, cmd["ack_status"], 1 if ok else 2)
                    await _set(nodes, cmd["ack_reason"], "" if ok else "zone_in_manual")
                    await _set(nodes, cmd["ack_seq"], seq)
                await asyncio.sleep(0.05)

        async with server:
            await _set(nodes, tm["system"]["mode"], "auto")
            await _set(nodes, tm["system"]["power_ok"], True)
            await _set(nodes, tm["system"]["tank_level_pct"], 72.5)
            await _set(nodes, z1["state"], 4)
            await _set(nodes, z1["run_source"], 2)  # started by the fallback program
            await _set(nodes, z1["runtime_sec"], 600)
            await _set(nodes, z1["target_sec"], 1800)
            await _set(nodes, z2["state"], 7)
            await _set(nodes, z2["fault"], 13)
            await _set(nodes, z2["panel_mode"], 1)
            await _set(nodes, tm["pumps"]["pump_well_01"]["power_kw"], 5.5)
            await _set(nodes, tm["system"]["alarm_word1"], 1 << (27 - 17))  # ALM-027 dry run
            logic = asyncio.create_task(plc_logic())
            adapter = OpcUaAdapter(tm, ack_timeout_s=3)
            try:
                await adapter.start(Layout())
                adapter.api_contact()
                st = {p["device_key"]: p["state_json"] for p in await adapter.read_state()}
                assert await _get(nodes, cmd["app_heartbeat"]) == 1

                z = st["zone_zone_rumman_1"]
                assert z["state"] == "running" and z["run_source"] == "fallback"
                assert z["runtime_sec"] == 600 and z["target_runtime_sec"] == 1800
                assert st["zone_zone_rumman_2"]["state"] == "faulted"
                assert st["zone_zone_rumman_2"]["panel_mode"] == "on"
                assert st["zone_zone_rumman_3"]["state"] == "off"  # not 'idle': an app state
                assert st["pump_pump_well_01"]["power_kw"] == pytest.approx(5.5)
                assert st["simulation_stats"]["tank_level_pct"] == pytest.approx(72.5)
                alarms = {(a["code"], a["zone_id"]) for a in st["plc_alarms"]["active"]}
                assert alarms == {("ALM-027", None), ("ALM-013", "zone_rumman_2")}

                res = await adapter.execute(
                    [
                        {
                            "id": "a",
                            "command_type": "start_zone",
                            "target_id": "zone_rumman_1",
                            "payload": {"duration_min": 20},
                        },
                        {
                            "id": "b",
                            "command_type": "start_zone",
                            "target_id": "zone_rumman_2",
                            "payload": {"duration_min": 5},
                        },
                    ]
                )
                assert res[0] == {"command_id": "a", "status": "completed"}
                assert res[1]["failure_reason"] == "zone_in_manual"
                assert await _get(nodes, cmd["duration_min"]) == 5

                await adapter.load_fallback(
                    [
                        {
                            "zone_id": "zone_enab",
                            "scheduled_start_farm": "2026-11-25T05:30:00",
                            "duration_min": 40,
                        }
                    ]
                )
                run1 = tm["fallback"]["runs"][0]
                assert [
                    await _get(nodes, run1[k])
                    for k in ("zone", "start_min", "duration_min", "weekday")
                ] == [11, 330, 40, 4]  # zone_enab = index 11, Wednesday = 4
                assert await _get(nodes, run1["valid"]) is True
                assert await _get(nodes, tm["fallback"]["runs"][1]["valid"]) is False
                assert await _get(nodes, tm["fallback"]["count"]) == 1
                assert await _get(nodes, tm["fallback"]["load_seq"]) == 1
            finally:
                await adapter.stop()
                logic.cancel()

    asyncio.run(run())


def test_a_tag_map_that_is_one_element_off_is_refused():
    async def run():
        server, tm, nodes = await _plc(_free_port())
        wrong = tm["zones"]["zone_rumman_2"]["config_id"]
        async with server:
            await _set(nodes, wrong, "zone_rumman_3")  # this node belongs to the next zone
            with pytest.raises(TagMapError, match="zone_rumman_2"):
                await OpcUaAdapter(tm).start(Layout())

    asyncio.run(run())


def test_example_tag_map_counts_array_elements_from_zero():
    """As the PLC's OPC UA server does (seen on PLCSIM): PLC zone n is element n - 1."""
    tm = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for tags in tm["zones"].values():
        assert f'"Zone"[{tags["index"] - 1}].' in tags["state"]
    runs = tm["fallback"]["runs"]
    assert [int(r["zone"].split("[")[1].split("]")[0]) for r in runs] == list(range(48))
