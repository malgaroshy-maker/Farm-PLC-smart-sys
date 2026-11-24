"""Adapter #2: Siemens S7-1200/1500 over OPC UA (Milestone G3 skeleton; tag map in G5).

Not used by default. Select it with CONTROLLER_ADAPTER=opcua and OPCUA_TAGMAP=<file>.
It is exercised in tests against an in-process asyncua server built from the same tag
map, so the read / command-handshake logic is real; the final node ids come from the
TIA Portal project in G5 and are validated with PLCSIM Advanced before any hardware.

Tag map (JSON, see opcua_tagmap.example.json):
  endpoint, system{mode, estop, tank_level_pct, main_pressure_bar, main_flow_m3h, heartbeat},
  zones{<zone_id>: {valve_open_fb, valve_closed_fb, flow_m3h, pressure_bar, moisture_pct,
                    running}},
  pumps{<pump_id>: {run_fb, fault, runtime_hours}},
  command{seq, type, target, duration_min, ack_seq, ack_status, ack_reason}

Command handshake (the PLC decides; interlocks live in the PLC):
  1. write type / target / duration_min, then seq = seq + 1
  2. the PLC validates, acts, and writes ack_status (1 = accepted, 2 = rejected) with
     ack_reason, then ack_seq = seq
  3. no ack within ack_timeout_s -> the command is reported "failed: plc_no_ack"
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from ..adapter import Layout
from ..state import utcnow

COMMAND_TYPES = {"start_zone": 1, "stop_zone": 2, "stop_all": 3, "reset_alarm": 4}


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
        self._last_heartbeat: Any = None
        self._events: list[dict] = []

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

    def _all_tags(self):
        t = self.tagmap
        for k, v in t["system"].items():
            yield f"system.{k}", v
        for zid, tags in t["zones"].items():
            for k, v in tags.items():
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

    # ── state ──────────────────────────────────────────────

    async def read_state(self) -> list[dict]:
        try:
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
        out = [
            item(
                "system_mode",
                {"mode": str(sys("mode", "auto")), "estop": bool(sys("estop", False))},
            ),
            item(
                "simulation_stats",
                {
                    "tank_level_pct": float(sys("tank_level_pct", 0.0)),
                    "main_pressure_bar": float(sys("main_pressure_bar", 0.0)),
                    "main_flow_m3h": float(sys("main_flow_m3h", 0.0)),
                    "refilling": False,
                },
            ),
        ]
        for zid in self.tagmap["zones"]:
            z = lambda k, d=None, _z=zid: v.get(f"zone.{_z}.{k}", d)  # noqa: E731
            running = bool(z("running", False))
            out.append(
                item(
                    f"zone_{zid}",
                    {
                        "zone_id": zid,
                        "state": "running" if running else "idle",
                        "health": "ok",
                        "flow_m3h": float(z("flow_m3h", 0.0)),
                        "pressure_bar": float(z("pressure_bar", 0.0)),
                        "moisture_pct": float(z("moisture_pct", 0.0)),
                        "last_updated": now,
                    },
                )
            )
            valve_id = "valve_" + zid.removeprefix("zone_")
            out.append(
                item(
                    f"valve_{valve_id}",
                    {
                        "valve_id": valve_id,
                        "zone_id": zid,
                        "status": "open" if z("valve_open_fb") else "closed",
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
                        "last_updated": now,
                    },
                )
            )
        return out

    # ── commands (handshake) ───────────────────────────────

    async def execute(self, commands: list[dict]) -> list[dict]:
        results = []
        for cmd in commands:
            cid = cmd.get("id") or cmd.get("command_id")
            status, reason = await self._send(cmd)
            res = {"command_id": cid, "status": status}
            if reason:
                res["reason"] = reason
            results.append(res)
        return results

    async def _send(self, cmd: dict) -> tuple[str, str | None]:
        from asyncua import ua

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
            seq = int(await n["command.seq"].read_value()) + 1
            await n["command.type"].write_value(
                ua.DataValue(ua.Variant(ctype, ua.VariantType.Int16))
            )
            await n["command.target"].write_value(
                ua.DataValue(ua.Variant(target, ua.VariantType.String))
            )
            dur = int(payload.get("duration_min") or 0)
            await n["command.duration_min"].write_value(
                ua.DataValue(ua.Variant(dur, ua.VariantType.Int16))
            )
            await n["command.seq"].write_value(ua.DataValue(ua.Variant(seq, ua.VariantType.Int32)))
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
