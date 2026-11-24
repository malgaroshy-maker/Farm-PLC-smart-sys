"""Milestone G3: the OPC UA adapter against a real (in-process) OPC UA server.

The server stands in for the S7 PLC: it exposes the tag map's nodes and answers the
command handshake like the PLC program will (accept a start, reject an interlocked one).
"""

import asyncio
import socket

import pytest

asyncua = pytest.importorskip("asyncua")
from asyncua import Server, ua  # noqa: E402

from src.adapter import Layout  # noqa: E402
from src.adapters.opcua_adapter import OpcUaAdapter  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _plc(port: int):
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://127.0.0.1:{port}")
    ns = await server.register_namespace("urn:test:plc")
    root = await server.nodes.objects.add_object(ns, "PLC")

    async def var(name, value, vtype):
        node = await root.add_variable(ua.NodeId(name, ns), name, ua.Variant(value, vtype))
        await node.set_writable()
        return node

    nodes = {
        "mode": await var("Mode", "auto", ua.VariantType.String),
        "estop": await var("EStop", False, ua.VariantType.Boolean),
        "tank": await var("Tank", 72.5, ua.VariantType.Double),
        "press": await var("Press", 2.4, ua.VariantType.Double),
        "flow": await var("Flow", 3.1, ua.VariantType.Double),
        "hb": await var("Heartbeat", 1, ua.VariantType.Int32),
        "z_run": await var("Z1Run", True, ua.VariantType.Boolean),
        "z_open": await var("Z1Open", True, ua.VariantType.Boolean),
        "z_closed": await var("Z1Closed", False, ua.VariantType.Boolean),
        "z_flow": await var("Z1Flow", 3.1, ua.VariantType.Double),
        "z_press": await var("Z1Press", 2.2, ua.VariantType.Double),
        "z_moist": await var("Z1Moist", 31.0, ua.VariantType.Double),
        "p_run": await var("PRun", True, ua.VariantType.Boolean),
        "p_fault": await var("PFault", False, ua.VariantType.Boolean),
        "p_hours": await var("PHours", 812.0, ua.VariantType.Double),
        "seq": await var("Seq", 0, ua.VariantType.Int16),
        "type": await var("Type", 0, ua.VariantType.Int16),
        "target": await var("Target", "", ua.VariantType.String),
        "dur": await var("Dur", 0, ua.VariantType.Int16),
        "ack_seq": await var("AckSeq", 0, ua.VariantType.Int16),
        "ack_status": await var("AckStatus", 0, ua.VariantType.Int16),
        "ack_reason": await var("AckReason", "", ua.VariantType.String),
    }

    def nid(name):
        return f"ns={ns};s={name}"

    tagmap = {
        "endpoint": f"opc.tcp://127.0.0.1:{port}",
        "system": {
            "mode": nid("Mode"),
            "estop": nid("EStop"),
            "tank_level_pct": nid("Tank"),
            "main_pressure_bar": nid("Press"),
            "main_flow_m3h": nid("Flow"),
            "heartbeat": nid("Heartbeat"),
        },
        "zones": {
            "zone_rumman_1": {
                "running": nid("Z1Run"),
                "valve_open_fb": nid("Z1Open"),
                "valve_closed_fb": nid("Z1Closed"),
                "flow_m3h": nid("Z1Flow"),
                "pressure_bar": nid("Z1Press"),
                "moisture_pct": nid("Z1Moist"),
            }
        },
        "pumps": {
            "pump_booster_01": {
                "run_fb": nid("PRun"),
                "fault": nid("PFault"),
                "runtime_hours": nid("PHours"),
            }
        },
        "command": {
            "seq": nid("Seq"),
            "type": nid("Type"),
            "target": nid("Target"),
            "duration_min": nid("Dur"),
            "ack_seq": nid("AckSeq"),
            "ack_status": nid("AckStatus"),
            "ack_reason": nid("AckReason"),
        },
    }

    async def plc_logic():
        """Answers the handshake like the PLC: start accepted, anything for zone_x rejected."""
        last = 0
        while True:
            seq = await nodes["seq"].read_value()
            if seq != last:
                last = seq
                target = await nodes["target"].read_value()
                ok = target != "zone_blocked"
                await nodes["ack_status"].write_value(
                    ua.Variant(1 if ok else 2, ua.VariantType.Int16)
                )
                await nodes["ack_reason"].write_value(
                    ua.Variant("" if ok else "interlock_pressure", ua.VariantType.String)
                )
                await nodes["ack_seq"].write_value(ua.Variant(seq, ua.VariantType.Int16))
            await asyncio.sleep(0.05)

    return server, tagmap, plc_logic


def test_reads_state_and_runs_the_command_handshake():
    async def run():
        port = _free_port()
        server, tagmap, plc_logic = await _plc(port)
        tagmap["zones"]["zone_blocked"] = tagmap["zones"]["zone_rumman_1"]
        async with server:
            logic = asyncio.create_task(plc_logic())
            adapter = OpcUaAdapter(tagmap, ack_timeout_s=3)
            try:
                await adapter.start(Layout(zones=[{"id": "zone_rumman_1"}, {"id": "zone_new"}]))
                assert adapter.link_ok()
                state = {p["device_key"]: p["state_json"] for p in await adapter.read_state()}
                assert state["simulation_stats"]["tank_level_pct"] == 72.5
                z = state["zone_zone_rumman_1"]
                assert z["state"] == "running" and z["moisture_pct"] == 31.0
                assert state["valve_valve_rumman_1"]["status"] == "open"
                assert state["pump_pump_booster_01"]["state"] == "running"

                res = await adapter.execute(
                    [
                        {
                            "id": "c1",
                            "command_type": "start_zone",
                            "target_id": "zone_rumman_1",
                            "payload": {"duration_min": 20},
                        },
                        {
                            "id": "c2",
                            "command_type": "start_zone",
                            "target_id": "zone_blocked",
                            "payload": {},
                        },
                        {
                            "id": "c3",
                            "command_type": "start_zone",
                            "target_id": "zone_new",
                            "payload": {},
                        },
                        {"id": "c4", "command_type": "fly", "target_id": "x"},
                    ]
                )
                by = {r["command_id"]: r for r in res}
                assert by["c1"]["status"] == "completed"
                assert by["c2"] == {
                    "command_id": "c2",
                    "status": "failed",
                    "failure_reason": "interlock_pressure",
                }
                assert by["c3"]["failure_reason"] == "no_tags_for:zone_new"
                assert by["c4"]["failure_reason"].startswith("unsupported_command")
            finally:
                await adapter.stop()
                logic.cancel()

    asyncio.run(run())


def test_no_ack_is_reported_as_failed():
    async def run():
        port = _free_port()
        server, tagmap, _logic = await _plc(port)
        async with server:  # no PLC logic running -> nobody acknowledges
            adapter = OpcUaAdapter(tagmap, ack_timeout_s=0.5)
            try:
                await adapter.start(Layout())
                res = await adapter.execute(
                    [{"id": "c1", "command_type": "stop_all", "target_id": ""}]
                )
                assert res == [
                    {"command_id": "c1", "status": "failed", "failure_reason": "plc_no_ack"}
                ]
            finally:
                await adapter.stop()

    asyncio.run(run())
