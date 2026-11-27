"""Adapter #3: a controller over Modbus TCP (Milestones G7 and G5).

For the farm PLC's Modbus TCP server (docs/PLC_PROGRAM.md) and for cheaper controllers
(S7-200 SMART, LOGO!, Delta AS). Select it with CONTROLLER_ADAPTER=modbus and
MODBUS_MAP=<file> (see modbus_map.example.json).

Register map: every value is one 16-bit holding register with an optional `scale`
(value = register / scale, signed). Zones have an `index` (1..16): the command target.

Command handshake (same as OPC UA; the PLC decides, interlocks live in the PLC):
  1. write type, target (zone index), duration_min, then seq = seq + 1
  2. the PLC acts or refuses and writes ack_status (1 = accepted, 2 = rejected) and
     ack_reason (a code, see plc_common.REASONS), then ack_seq = seq
  3. no ack within ack_timeout_s -> "failed: plc_no_ack"
The PLC runs a start for exactly `duration_min` on its own timer, so a lost link can
never leave a valve open.

G5 additions (all optional in the map, so simpler controllers still work):
  - zone `state` register: state + 256 * run source (plc_common.ZONE_STATES / RUN_SOURCES),
    `runtime_sec`, `target_sec` (seconds, so the app's timer runs smoothly), `fault`
  - system `alarm_word0..2`: the PLC's alarm bits -> the app's `plc_alarms`
  - command `app_heartbeat`: written after every successful push to the API, so the PLC
    runs its stored schedule when the *server* is down (not just this gateway)
  - `fallback`: the next 24 h of runs written into the PLC (seq bumped last)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from ..adapter import Layout
from ..modbus_tcp import ModbusError, ModbusTcpClient
from ..state import utcnow
from . import plc_common as pc

COMMAND_TYPES = {"start_zone": 1, "stop_zone": 2, "stop_all": 3, "reset_alarm": 4}
REASONS = pc.REASONS
ALARM_WORDS = ("alarm_word0", "alarm_word1", "alarm_word2")


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
        self._heartbeat = 0
        self._heartbeat_due = False
        self._clock_due = pc.ClockSetTimer()
        self._zone_index = {
            zid: int(z["index"]) for zid, z in regmap["zones"].items() if "index" in z
        }

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

    async def probe(self) -> None:
        """Link down: try the PLC again (the gateway calls this every second until it answers)."""
        try:
            await self.client.read_holding(self._addr["command.seq"][0], 1)
        except Exception:
            return
        print("[MODBUS] PLC answering again")
        self._ok = True

    def on_clock(self, payload: dict) -> None:
        return None  # the PLC runs on real time

    def api_contact(self) -> None:
        """The API took our last push: tell the PLC the app is alive (written on the next read)."""
        self._heartbeat_due = True

    # ── state ──────────────────────────────────────────────

    async def _read_raw(self) -> dict[int, int]:
        addrs = sorted({a for a, _ in self._addr.values()})
        values: dict[int, int] = {}
        start = addrs[0]
        while start <= addrs[-1]:
            count = min(120, addrs[-1] - start + 1)
            for i, v in enumerate(await self.client.read_holding(start, count)):
                values[start + i] = v
            start += count
        return values

    async def _read_all(self) -> tuple[dict[str, float], dict[str, int]]:
        raw = await self._read_raw()
        scaled, words = {}, {}
        for key, (a, scale) in self._addr.items():
            r = raw[a]
            words[key] = r
            scaled[key] = (r - 0x10000 if r >= 0x8000 else r) / scale  # signed 16-bit
        return scaled, words

    async def _send_heartbeat(self) -> None:
        a = self._addr.get("command.app_heartbeat")
        if a is None or not self._heartbeat_due:
            return
        self._heartbeat = (self._heartbeat + 1) % 30000
        await self.client.write_register(a[0], self._heartbeat)
        self._heartbeat_due = False

    async def read_state(self) -> list[dict]:
        try:
            await self._send_heartbeat()
            try:
                v, raw = await self._read_all()
            except (TimeoutError, OSError, ModbusError):
                v, raw = await self._read_all()  # one slow reply: retry once on a fresh connection
        except Exception as exc:
            self._ok = False
            print(f"[MODBUS] read failed: {type(exc).__name__}")
            return []
        self._ok = True
        now = utcnow().isoformat()

        def item(key: str, data: dict) -> dict:
            return {"device_key": key, "state_json": data, "updated_at": now}

        sys = lambda k, d=0.0: v.get(f"system.{k}", d)  # noqa: E731
        stats = {
            "tank_level_pct": sys("tank_level_pct"),
            "main_pressure_bar": sys("main_pressure_bar"),
            "main_flow_m3h": sys("main_flow_m3h"),
            "refilling": bool(sys("refilling")),
        }
        for opt in ("well_level_m", "filter_dp_bar"):
            if f"system.{opt}" in v:
                stats[opt] = sys(opt)
        mode_extra = {}
        skew = await self._check_clock(v, raw)
        if skew is not None:
            mode_extra["plc_clock_skew_sec"] = skew
        if "system.hmi_stop_all_count" in v:
            mode_extra["hmi_stop_all_count"] = int(sys("hmi_stop_all_count"))
        out = [
            item(
                "system_mode",
                {
                    "mode": pc.MODES.get(int(sys("mode", 1)), "auto"),
                    "estop": bool(sys("estop")),
                    "power_ok": bool(sys("power_ok", 1)),
                    "fallback_active": bool(sys("fallback_active")),
                    **mode_extra,
                },
            ),
            item("simulation_stats", stats),
        ]

        zone_faults: dict[str, int] = {}
        for zid in self.map["zones"]:
            z = lambda k, d=0.0, _z=zid: v.get(f"zone.{_z}.{k}", d)  # noqa: E731
            state_key = f"zone.{zid}.state"
            if state_key in raw:
                code = raw[state_key]
                state, source = pc.zone_state(code & 0xFF), pc.RUN_SOURCES.get(code >> 8)
            else:  # a simple controller: only a running bit
                state, source = ("running" if z("running") else "off"), None
            fault = int(z("fault"))
            if fault:  # the PLC reports a zone fault while its cause is live; the app latches it
                zone_faults[zid] = fault
            data = {
                "zone_id": zid,
                "state": state,
                "health": "warning" if state == "faulted" else "healthy",
                "flow_m3h": z("flow_m3h"),
                "pressure_bar": z("pressure_bar"),
                # the PLC never writes this field, so 0 means nothing measures it, not "0 %"
                "moisture_pct": z("moisture_pct", None) or None,
                "panel_mode": pc.PANEL_ZONE.get(int(z("panel_mode")), "auto"),
                "run_source": source if state not in ("off", "completed") else None,
                "last_updated": now,
            }
            if f"zone.{zid}.runtime_sec" in v:
                data["runtime_sec"] = z("runtime_sec")
                data["target_runtime_sec"] = z("target_sec")
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
        for pid in self.map["pumps"]:
            p = lambda k, d=0.0, _p=pid: v.get(f"pump.{_p}.{k}", d)  # noqa: E731
            feedback = p("run_fb", None)
            run, fault = bool(feedback), bool(p("fault"))
            out.append(
                item(
                    f"pump_{pid}",
                    {
                        "pump_id": pid,
                        "state": "faulted" if fault else ("running" if run else "stopped"),
                        "run_fb": run,
                        "run_fb_observed": feedback is not None,
                        "fault": fault,
                        "runtime_hours": p("runtime_hours"),
                        "panel_mode": pc.PANEL_PUMP.get(int(p("panel_mode")), "auto"),
                        "power_kw": p("power_kw"),
                        "current_a": p("current_a"),
                        "energy_kwh_today": p("energy_kwh_today"),
                        "last_updated": now,
                    },
                )
            )

        if all(f"system.{w}" in raw for w in ALARM_WORDS):
            active = pc.alarm_bits([raw[f"system.{w}"] for w in ALARM_WORDS])
            out.append(item("plc_alarms", {"active": pc.plc_alarms(active, zone_faults)}))
        return out

    # ── PLC clock ──────────────────────────────────────────

    async def _check_clock(self, values: dict, raw: dict) -> int | None:
        """Seconds the PLC's local time is ahead of the farm's; sets the PLC clock when it is off.

        None for a controller that does not publish its clock.
        """
        if not raw.get("system.clock_year"):
            return None
        now = self._farm_wall_clock()
        skew = pc.clock_skew_sec(
            [raw[f"system.clock_{k}"] for k in ("year", "month_day", "hour_minute", "second")], now
        )
        if skew is not None and self._clock_due.take(skew):
            await self._set_clock(now, skew)
        return skew

    @staticmethod
    def _farm_wall_clock() -> datetime:
        return pc.farm_wall_clock()

    async def _set_clock(self, now: datetime, skew: int) -> None:
        clock = self.map.get("clock")
        if not clock:
            return
        try:
            await self.client.write_registers(
                int(clock["base"]),
                [now.year, now.month, now.day, now.hour, now.minute, now.second],
            )
            seq_addr = int(clock["seq"]["hr"])
            seq = (await self.client.read_holding(seq_addr, 1))[0]
            # last: the PLC takes the time when this changes
            await self.client.write_register(seq_addr, seq % 30000 + 1)
            print(f"[MODBUS] PLC clock was {skew:+d} s off farm time: set")
        except Exception as exc:  # the next check tries again; the API raises ALM-051
            print(f"[MODBUS] clock write failed: {type(exc).__name__}")

    # ── fallback program (G7/G5) ───────────────────────────

    async def load_fallback(self, runs: list[dict]) -> None:
        fb = self.map.get("fallback")
        if not fb:
            return
        rows = pc.fallback_runs(runs, self._zone_index, int(fb.get("max_runs", 20)))
        try:
            base = int(fb["base"])
            if rows:
                words = [w for row in rows for w in row]
                await self.client.write_registers(base, words)
            await self.client.write_register(int(fb["count"]["hr"]), len(rows))
            seq_addr = int(fb["seq"]["hr"])
            seq = (await self.client.read_holding(seq_addr, 1))[0]
            await self.client.write_register(seq_addr, (seq + 1) & 0x7FFF)  # last: the PLC commits
        except Exception as exc:
            self._ok = False
            print(f"[MODBUS] fallback write failed: {type(exc).__name__}")

    # ── commands (handshake) ───────────────────────────────

    async def execute(self, commands: list[dict]) -> list[dict]:
        results = []
        for cmd in commands:
            status, reason = await self._send(cmd)
            res = {"command_id": cmd.get("id") or cmd.get("command_id"), "status": status}
            if reason:
                res["failure_reason"] = reason
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
            seq = ((await self.client.read_holding(c["command.seq"], 1))[0] + 1) & 0x7FFF
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
