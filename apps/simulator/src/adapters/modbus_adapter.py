"""Adapter #3: a controller over Modbus TCP (Milestone G7).

For the cheaper controllers in the hardware report (Siemens S7-200 SMART or LOGO!, Delta AS,
or an S7-1200 used without OPC UA). Select it with CONTROLLER_ADAPTER=modbus and
MODBUS_MAP=<file> (see modbus_map.example.json).

Register map: every value is one 16-bit holding register with an optional `scale`
(value = register / scale). Zones have an `index` (1..n): the command target the PLC uses.

Command handshake (same as OPC UA; the PLC decides, interlocks live in the PLC):
  1. write type, target (zone index), duration_min, then seq = seq + 1
  2. the PLC acts or refuses and writes ack_status (1 = accepted, 2 = rejected) and
     ack_reason (a code, see REASONS), then ack_seq = seq
  3. no ack within ack_timeout_s -> "failed: plc_no_ack"
The PLC also runs a start for exactly `duration_min` on its own timer, so a lost link can
never leave a valve open (the same rule the radio boxes follow).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from ..adapter import Layout
from ..modbus_tcp import ModbusTcpClient
from ..state import utcnow

COMMAND_TYPES = {"start_zone": 1, "stop_zone": 2, "stop_all": 3, "reset_alarm": 4}
MODES = {0: "off", 1: "auto", 2: "manual", 3: "maintenance"}
PANEL_ZONE = {0: "auto", 1: "on", 2: "off"}
PANEL_PUMP = {0: "auto", 1: "hand", 2: "off"}
REASONS = {
    1: "interlock",
    2: "zone_in_manual",
    3: "no_power",
    4: "pump_unavailable",
    5: "tank_low",
    6: "estop_active",
    9: "plc_rejected",
}


class MapError(ValueError):
    pass


def _resolve(path: str | Path) -> Path:
    """A relative path may be given from the project root (as in .env) or from apps/simulator."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        root = Path(__file__).resolve().parents[4] / p
        if root.exists():
            return root
    return p


def load_map(path: str | Path) -> dict:
    data = json.loads(_resolve(path).read_text(encoding="utf-8"))
    for key in ("host", "system", "zones", "pumps", "command"):
        if key not in data:
            raise MapError(f"register map is missing '{key}'")
    return data


class ModbusAdapter:
    name = "modbus"

    def __init__(self, regmap: dict, ack_timeout_s: float = 5.0):
        self.map = regmap
        self.ack_timeout_s = ack_timeout_s
        self.client = ModbusTcpClient(
            regmap["host"], int(regmap.get("port", 502)), int(regmap.get("unit", 1))
        )
        self._ok = False
        self._events: list[dict] = []
        self._addr = self._addresses()

    def _addresses(self) -> dict[str, tuple[int, float]]:
        out = {}

        def add(prefix: str, tags: dict):
            for k, spec in tags.items():
                if isinstance(spec, dict) and "hr" in spec:
                    out[f"{prefix}{k}"] = (int(spec["hr"]), float(spec.get("scale", 1)))

        add("system.", self.map["system"])
        for zid, tags in self.map["zones"].items():
            add(f"zone.{zid}.", tags)
        for pid, tags in self.map["pumps"].items():
            add(f"pump.{pid}.", tags)
        add("command.", self.map["command"])
        return out

    # ── connection ─────────────────────────────────────────

    async def start(self, layout: Layout) -> None:
        await self.client.connect()
        missing = [
            z["id"]
            for z in layout.zones
            if z.get("enabled", True) and z["id"] not in self.map["zones"]
        ]
        if missing:
            print(f"[MODBUS] zones without registers (not controllable): {', '.join(missing)}")
        self._ok = True

    async def stop(self) -> None:
        await self.client.close()
        self._ok = False

    def link_ok(self) -> bool:
        return self._ok

    def on_clock(self, payload: dict) -> None:
        return None  # the PLC runs on real time

    # ── state ──────────────────────────────────────────────

    async def _read_all(self) -> dict[str, float]:
        addrs = sorted({a for a, _ in self._addr.values()})
        values: dict[int, int] = {}
        start = addrs[0]
        while start <= addrs[-1]:
            count = min(120, addrs[-1] - start + 1)
            for i, v in enumerate(await self.client.read_holding(start, count)):
                values[start + i] = v
            start += count
        out = {}
        for key, (a, scale) in self._addr.items():
            raw = values[a]
            raw = raw - 0x10000 if raw >= 0x8000 else raw  # signed 16-bit
            out[key] = raw / scale
        return out

    async def read_state(self) -> list[dict]:
        try:
            v = await self._read_all()
        except Exception as exc:
            self._ok = False
            print(f"[MODBUS] read failed: {type(exc).__name__}")
            return []
        self._ok = True
        now = utcnow().isoformat()

        def item(key: str, data: dict) -> dict:
            return {"device_key": key, "state_json": data, "updated_at": now}

        sys = lambda k, d=0.0: v.get(f"system.{k}", d)  # noqa: E731
        out = [
            item(
                "system_mode",
                {
                    "mode": MODES.get(int(sys("mode", 1)), "auto"),
                    "estop": bool(sys("estop")),
                    "power_ok": bool(sys("power_ok", 1)),
                    "fallback_active": bool(sys("fallback_active")),
                },
            ),
            item(
                "simulation_stats",
                {
                    "tank_level_pct": sys("tank_level_pct"),
                    "main_pressure_bar": sys("main_pressure_bar"),
                    "main_flow_m3h": sys("main_flow_m3h"),
                    "refilling": False,
                    **({"well_level_m": sys("well_level_m")} if "system.well_level_m" in v else {}),
                    **(
                        {"filter_dp_bar": sys("filter_dp_bar")}
                        if "system.filter_dp_bar" in v
                        else {}
                    ),
                },
            ),
        ]
        for zid in self.map["zones"]:
            z = lambda k, d=0.0, _z=zid: v.get(f"zone.{_z}.{k}", d)  # noqa: E731
            running = bool(z("running"))
            out.append(
                item(
                    f"zone_{zid}",
                    {
                        "zone_id": zid,
                        "state": "running" if running else "idle",
                        "health": "ok",
                        "flow_m3h": z("flow_m3h"),
                        "pressure_bar": z("pressure_bar"),
                        "moisture_pct": z("moisture_pct", 0.0),
                        "panel_mode": PANEL_ZONE.get(int(z("panel_mode")), "auto"),
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
        for pid in self.map["pumps"]:
            p = lambda k, d=0.0, _p=pid: v.get(f"pump.{_p}.{k}", d)  # noqa: E731
            run, fault = bool(p("run_fb")), bool(p("fault"))
            out.append(
                item(
                    f"pump_{pid}",
                    {
                        "pump_id": pid,
                        "state": "faulted" if fault else ("running" if run else "stopped"),
                        "run_fb": run,
                        "fault": fault,
                        "runtime_hours": p("runtime_hours"),
                        "panel_mode": PANEL_PUMP.get(int(p("panel_mode")), "auto"),
                        "power_kw": p("power_kw"),
                        "current_a": p("current_a"),
                        "last_updated": now,
                    },
                )
            )
        return out

    # ── commands (handshake) ───────────────────────────────

    async def execute(self, commands: list[dict]) -> list[dict]:
        results = []
        for cmd in commands:
            status, reason = await self._send(cmd)
            res = {"command_id": cmd.get("id") or cmd.get("command_id"), "status": status}
            if reason:
                res["reason"] = reason
            results.append(res)
        return results

    async def _send(self, cmd: dict) -> tuple[str, str | None]:
        ctype = COMMAND_TYPES.get(cmd.get("command_type", ""))
        if ctype is None:
            return "failed", f"unsupported_command:{cmd.get('command_type')}"
        target_id = cmd.get("target_id") or ""
        target = 0
        if cmd.get("command_type") in ("start_zone", "stop_zone"):
            zone = self.map["zones"].get(target_id)
            if not zone or "index" not in zone:
                return "failed", f"no_registers_for:{target_id}"
            target = int(zone["index"])
        payload = cmd.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        c = {k: a for k, (a, _s) in self._addr.items() if k.startswith("command.")}
        try:
            seq = ((await self.client.read_holding(c["command.seq"], 1))[0] + 1) & 0xFFFF
            await self.client.write_register(c["command.type"], ctype)
            await self.client.write_register(c["command.target"], target)
            await self.client.write_register(
                c["command.duration_min"], int(payload.get("duration_min") or 0)
            )
            await self.client.write_register(c["command.seq"], seq)
            deadline = time.monotonic() + self.ack_timeout_s
            while time.monotonic() < deadline:
                if (await self.client.read_holding(c["command.ack_seq"], 1))[0] == seq:
                    st = (await self.client.read_holding(c["command.ack_status"], 1))[0]
                    if st == 1:
                        return "completed", None
                    code = (await self.client.read_holding(c["command.ack_reason"], 1))[0]
                    return "failed", REASONS.get(code, f"plc_rejected:{code}")
                await asyncio.sleep(0.1)
            return "failed", "plc_no_ack"
        except Exception as exc:
            self._ok = False
            return "failed", f"modbus_error:{type(exc).__name__}"

    async def drain_events(self) -> list[dict]:
        ev, self._events = self._events, []
        return ev
