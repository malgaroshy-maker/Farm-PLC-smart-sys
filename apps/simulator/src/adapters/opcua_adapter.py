"""Adapter #2: Siemens S7-1500 over OPC UA (G3 skeleton; G5: the farm PLC's data blocks).

Select it with CONTROLLER_ADAPTER=opcua and OPCUA_TAGMAP=<file>. The example tag map
(opcua_tagmap.example.json) points at the DBs of docs/PLC_PROGRAM.md / plc/src.
It is exercised in tests against an in-process asyncua server built from the same tag map,
so the read / command-handshake logic is real; PLCSIM Advanced validates the node ids.

Tag map (JSON):
  endpoint
  system{mode, estop, tank_level_pct, main_pressure_bar, main_flow_m3h, heartbeat,
         power_ok, fallback_active, well_level_m, filter_dp_bar, refilling,
         alarm_word0..2}                                  (G5 keys are optional)
  zones{<zone_id>: {index, running, valve_open_fb, flow_m3h, pressure_bar, moisture_pct,
                    state, run_source, panel_mode, runtime_sec, target_sec, fault}}
  pumps{<pump_id>: {run_fb, fault, runtime_hours, panel_mode, power_kw, current_a,
                    energy_kwh_today}}
  command{seq, type, target, duration_min, ack_seq, ack_status, ack_reason, app_heartbeat}
  fallback{count, load_seq, runs: [{zone, start_min, duration_min, weekday, valid}, ...]}

Command handshake (the PLC decides; interlocks live in the PLC):
  1. write type / target (zone id) / duration_min, then seq = seq + 1
  2. the PLC validates, acts, and writes ack_status (1 = accepted, 2 = rejected) with
     ack_reason, then ack_seq = seq
  3. no ack within ack_timeout_s -> the command is reported "failed: plc_no_ack"
S7 `Int` is 16-bit: every integer is written as Int16, or the PLC rejects the write.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from ..adapter import Layout
from ..state import utcnow
from . import plc_common as pc

COMMAND_TYPES = {"start_zone": 1, "stop_zone": 2, "stop_all": 3, "reset_alarm": 4}
NOT_NODES = {"index"}  # tag-map keys that are settings, not node ids
ALARM_WORDS = ("alarm_word0", "alarm_word1", "alarm_word2")


class TagMapError(ValueError):
    pass


def _resolve(path: str | Path) -> Path:
    """A relative path may be given from the project root (as in .env) or from apps/simulator."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        root = Path(__file__).resolve().parents[4] / p
        if root.exists():
            return root
    return p


def load_tagmap(path: str | Path) -> dict:
    data = json.loads(_resolve(path).read_text(encoding="utf-8"))
    for key in ("endpoint", "system", "zones", "pumps", "command"):
        if key not in data:
            raise TagMapError(f"tag map is missing '{key}'")
    return data


class OpcUaAdapter:
    name = "opcua"

    def __init__(self, tagmap: dict, ack_timeout_s: float = 5.0):
        self.tagmap = tagmap
        self.ack_timeout_s = ack_timeout_s
        self.client: Any = None
        self._nodes: dict[str, Any] = {}
        self._ok = False
        self._events: list[dict] = []
        self._heartbeat = 0
        self._heartbeat_due = False
        self._zone_index = {
            zid: int(z["index"]) for zid, z in tagmap["zones"].items() if "index" in z
        }

    # ── connection ─────────────────────────────────────────

    async def start(self, layout: Layout) -> None:
        from asyncua import Client  # optional dependency: pip install asyncua

        self.client = Client(url=self.tagmap["endpoint"], timeout=4)
        await self.client.connect()
        for path, node_id in self._all_tags():
            self._nodes[path] = self.client.get_node(node_id)
        missing = [
            z["id"]
            for z in layout.zones
            if z.get("enabled", True) and z["id"] not in self.tagmap["zones"]
        ]
        if missing:
            print(f"[OPCUA] zones without tags (not controllable): {', '.join(missing)}")
        self._ok = True

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.disconnect()
        self._ok = False

    def link_ok(self) -> bool:
        return self._ok

    def on_clock(self, payload: dict) -> None:
        return None  # the PLC runs on real time

    def api_contact(self) -> None:
        """The API took our last push: tell the PLC the app is alive (written on the next read)."""
        self._heartbeat_due = True

    def _all_tags(self):
        t = self.tagmap
        for k, v in t["system"].items():
            yield f"system.{k}", v
        for zid, tags in t["zones"].items():
            for k, v in tags.items():
                if k not in NOT_NODES:
                    yield f"zone.{zid}.{k}", v
        for pid, tags in t["pumps"].items():
            for k, v in tags.items():
                yield f"pump.{pid}.{k}", v
        for k, v in t["command"].items():
            yield f"command.{k}", v

    async def _read_many(self, paths: list[str]) -> dict[str, Any]:
        nodes = [self._nodes[p] for p in paths]
        values = await self.client.read_values(nodes)
        return dict(zip(paths, values, strict=True))

    async def _write(self, node: Any, value: Any, vtype: str) -> None:
        from asyncua import ua

        await node.write_value(ua.DataValue(ua.Variant(value, getattr(ua.VariantType, vtype))))

    # ── state ──────────────────────────────────────────────

    async def read_state(self) -> list[dict]:
        try:
            if self._heartbeat_due and "command.app_heartbeat" in self._nodes:
                self._heartbeat = (self._heartbeat + 1) % 30000
                await self._write(self._nodes["command.app_heartbeat"], self._heartbeat, "Int16")
                self._heartbeat_due = False
            paths = [p for p in self._nodes if not p.startswith("command.")]
            v = await self._read_many(paths)
        except Exception as exc:
            self._ok = False
            print(f"[OPCUA] read failed: {type(exc).__name__}")
            return []
        self._ok = True
        now = utcnow().isoformat()

        def item(key: str, data: dict) -> dict:
            return {"device_key": key, "state_json": data, "updated_at": now}

        sys = lambda k, d=None: v.get(f"system.{k}", d)  # noqa: E731
        stats = {
            "tank_level_pct": float(sys("tank_level_pct", 0.0)),
            "main_pressure_bar": float(sys("main_pressure_bar", 0.0)),
            "main_flow_m3h": float(sys("main_flow_m3h", 0.0)),
            "refilling": bool(sys("refilling", False)),
        }
        for opt in ("well_level_m", "filter_dp_bar"):
            if f"system.{opt}" in v:
                stats[opt] = float(sys(opt))
        out = [
            item(
                "system_mode",
                {
                    "mode": str(sys("mode", "auto")),
                    "estop": bool(sys("estop", False)),
                    "power_ok": bool(sys("power_ok", True)),
                    "fallback_active": bool(sys("fallback_active", False)),
                },
            ),
            item("simulation_stats", stats),
        ]

        zone_faults: dict[str, int] = {}
        for zid in self.tagmap["zones"]:
            z = lambda k, d=None, _z=zid: v.get(f"zone.{_z}.{k}", d)  # noqa: E731
            if f"zone.{zid}.state" in v:
                state = pc.zone_state(int(z("state")))
                source = pc.RUN_SOURCES.get(int(z("run_source", 0)))
            else:  # a tag map with only a running bit
                state, source = ("running" if z("running", False) else "off"), None
            if int(z("fault", 0) or 0):  # reported fault (live); the app latches it
                zone_faults[zid] = int(z("fault"))
            data = {
                "zone_id": zid,
                "state": state,
                "health": "warning" if state == "faulted" else "healthy",
                "flow_m3h": float(z("flow_m3h", 0.0)),
                "pressure_bar": float(z("pressure_bar", 0.0)),
                "moisture_pct": float(z("moisture_pct", 0.0)),
                "panel_mode": pc.PANEL_ZONE.get(int(z("panel_mode", 0)), "auto"),
                "run_source": source if state not in ("off", "completed") else None,
                "last_updated": now,
            }
            if f"zone.{zid}.runtime_sec" in v:
                data["runtime_sec"] = float(z("runtime_sec"))
                data["target_runtime_sec"] = float(z("target_sec", 0))
            out.append(item(f"zone_{zid}", data))
            valve_id = "valve_" + zid.removeprefix("zone_")
            out.append(
                item(
                    f"valve_{valve_id}",
                    {
                        "valve_id": valve_id,
                        "zone_id": zid,
                        "status": "open" if z("valve_open_fb") else "closed",
                        "last_command": "open" if z("valve_open_fb") else "close",
                        "last_updated": now,
                    },
                )
            )
        for pid in self.tagmap["pumps"]:
            p = lambda k, d=None, _p=pid: v.get(f"pump.{_p}.{k}", d)  # noqa: E731
            run = bool(p("run_fb", False))
            out.append(
                item(
                    f"pump_{pid}",
                    {
                        "pump_id": pid,
                        "state": "faulted" if p("fault") else ("running" if run else "stopped"),
                        "run_fb": run,
                        "fault": bool(p("fault", False)),
                        "runtime_hours": float(p("runtime_hours", 0.0)),
                        "panel_mode": pc.PANEL_PUMP.get(int(p("panel_mode", 0)), "auto"),
                        "power_kw": float(p("power_kw", 0.0)),
                        "current_a": float(p("current_a", 0.0)),
                        "energy_kwh_today": float(p("energy_kwh_today", 0.0)),
                        "last_updated": now,
                    },
                )
            )
        if all(f"system.{w}" in v for w in ALARM_WORDS):
            active = pc.alarm_bits([int(v[f"system.{w}"]) & 0xFFFF for w in ALARM_WORDS])
            out.append(item("plc_alarms", {"active": pc.plc_alarms(active, zone_faults)}))
        return out

    # ── fallback program (G7/G5) ───────────────────────────

    async def load_fallback(self, runs: list[dict]) -> None:
        fb = self.tagmap.get("fallback")
        if not fb or self.client is None:
            return
        slots = fb["runs"]
        rows = pc.fallback_runs(runs, self._zone_index, len(slots))
        get = self.client.get_node
        try:
            for i, slot in enumerate(slots):
                if i < len(rows):
                    zone, start_min, dur, weekday = rows[i]
                    await self._write(get(slot["zone"]), zone, "Int16")
                    await self._write(get(slot["start_min"]), start_min, "Int16")
                    await self._write(get(slot["duration_min"]), dur, "Int16")
                    await self._write(get(slot["weekday"]), weekday, "Int16")
                    await self._write(get(slot["valid"]), True, "Boolean")
                else:
                    await self._write(get(slot["valid"]), False, "Boolean")
            await self._write(get(fb["count"]), len(rows), "Int16")
            seq_node = get(fb["load_seq"])
            seq = int(await seq_node.read_value())
            await self._write(seq_node, (seq + 1) % 30000, "Int16")  # last: the PLC commits
        except Exception as exc:
            self._ok = False
            print(f"[OPCUA] fallback write failed: {type(exc).__name__}")

    # ── commands (handshake) ───────────────────────────────

    async def execute(self, commands: list[dict]) -> list[dict]:
        results = []
        for cmd in commands:
            cid = cmd.get("id") or cmd.get("command_id")
            status, reason = await self._send(cmd)
            res = {"command_id": cid, "status": status}
            if reason:
                res["failure_reason"] = reason
            results.append(res)
        return results

    async def _send(self, cmd: dict) -> tuple[str, str | None]:
        ctype = COMMAND_TYPES.get(cmd.get("command_type", ""))
        if ctype is None:
            return "failed", f"unsupported_command:{cmd.get('command_type')}"
        target = cmd.get("target_id") or ""
        if (
            cmd.get("command_type") in ("start_zone", "stop_zone")
            and target not in self.tagmap["zones"]
        ):
            return "failed", f"no_tags_for:{target}"
        payload = cmd.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        n = self._nodes
        try:
            seq = (int(await n["command.seq"].read_value()) + 1) % 30000
            await self._write(n["command.type"], ctype, "Int16")
            await self._write(n["command.target"], target, "String")
            await self._write(
                n["command.duration_min"], int(payload.get("duration_min") or 0), "Int16"
            )
            await self._write(n["command.seq"], seq, "Int16")
            deadline = time.monotonic() + self.ack_timeout_s
            while time.monotonic() < deadline:
                if int(await n["command.ack_seq"].read_value()) == seq:
                    st = int(await n["command.ack_status"].read_value())
                    if st == 1:
                        return "completed", None
                    reason = str(await n["command.ack_reason"].read_value() or "plc_rejected")
                    return "failed", reason
                await asyncio.sleep(0.1)
            return "failed", "plc_no_ack"
        except Exception as exc:
            self._ok = False
            return "failed", f"opcua_error:{type(exc).__name__}"

    async def drain_events(self) -> list[dict]:
        ev, self._events = self._events, []
        return ev
