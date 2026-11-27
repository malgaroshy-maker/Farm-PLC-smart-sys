"""Virtual farm PLC (G5): the physics simulator behind the real PLC's Modbus TCP interface.

Until TIA Portal / PLCSIM can run the SCL program, this lets the whole app run the *PLC path*:
the gateway uses the production Modbus adapter against registers laid out exactly like
plc/src/11_ModbusMap.scl, with the same handshake, reason codes, heartbeat watchdog and
fallback list. The simulator engine plays both the farm and the PLC's logic.

Simulation-only commands (panel switches, injected faults, mode) are not something a PLC
receives over Modbus: like PLCSIM's inputs, they go straight to the simulated farm.

    CONTROLLER_ADAPTER=modbus VIRTUAL_PLC=1  python -m src.main
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from .adapters import plc_common as pc
from .adapters.modbus_adapter import ModbusAdapter
from .engine import SimulatorEngine
from .modbus_tcp import ModbusTcpServer
from .state import utcnow

SIM_ONLY = {"set_panel", "inject_fault", "set_mode"}
MODE_CODES = {v: k for k, v in pc.MODES.items()}
PANEL_ZONE_CODES = {v: k for k, v in pc.PANEL_ZONE.items()}
PANEL_PUMP_CODES = {v: k for k, v in pc.PANEL_PUMP.items()}
SOURCE_CODES = {v: k for k, v in pc.RUN_SOURCES.items()}
STATE_CODES = {name: i for i, name in enumerate(pc.ZONE_STATES)}
STATE_CODES.update({"queued": 1, "warning": 4})  # app states the PLC folds into its own
TYPES = {1: "start_zone", 2: "stop_zone", 3: "stop_all", 4: "reset_alarm"}


def reason_code(text: str | None) -> int:
    """The engine explains a refusal in words; the PLC answers with a code."""
    t = (text or "").lower()
    for needle, code in (
        ("emergency", 6),
        ("mains", 3),
        ("panel", 2),
        ("already active", 7),
        ("tank", 5),
        ("pump unavailable", 4),
        ("not found", 8),
    ):
        if needle in t:
            return code
    return 9


def _w(value: float, scale: float = 1.0) -> int:
    """Real -> signed 16-bit register."""
    return max(-32768, min(32767, round(value * scale))) & 0xFFFF


class VirtualPlc:
    def __init__(self, engine: SimulatorEngine, regmap: dict):
        self.engine = engine
        self.map = regmap
        self.server = ModbusTcpServer(size=400)
        self.zone_by_index = {
            int(z["index"]): zid for zid, z in regmap["zones"].items() if "index" in z
        }
        self.running = False
        self._seq = self._hb = self._fb_seq = 0

    def hr(self, section: str, key: str, item: str | None = None) -> int | None:
        sec = self.map.get(section, {})
        spec = (sec.get(item, {}) if item else sec).get(key)
        return int(spec["hr"]) if isinstance(spec, dict) and "hr" in spec else None

    async def start(self, host: str = "127.0.0.1", port: int = 1502) -> int:
        port = await self.server.start(host, port)
        r = self.server.regs
        self._seq, self._hb, self._fb_seq = r[300], r[307], r[318]
        return port

    async def stop(self) -> None:
        self.running = False
        await self.server.stop()

    async def run_loop(self, period: float = 0.2) -> None:
        self.running = True
        print("[VPLC] Virtual farm PLC serving Modbus TCP")
        while self.running:
            self.sync()
            await asyncio.sleep(period)

    def press_hmi_stop_all(self) -> None:
        """The HMI's Stop all button, like FB_Link: stop the zones and count the press."""
        self.engine.process_commands(
            [{"id": f"hmi-{self.server.regs[15] + 1}", "command_type": "stop_all", "target_id": ""}]
        )
        self.server.regs[15] = self.server.regs[15] % 29999 + 1

    # ── one scan ───────────────────────────────────────────

    def sync(self) -> None:
        self._inputs()
        self._outputs()

    def _inputs(self) -> None:
        r = self.server.regs
        if r[307] != self._hb:  # the gateway beats only after the API took its push
            self._hb = r[307]
            self.engine.note_api_contact()
        if r[318] != self._fb_seq:
            self._fb_seq = r[318]
            self.engine.load_fallback(self._fallback_runs())
        if r[300] != self._seq:
            self._seq = r[300]
            self._command(r[301], r[302], r[303])

    def _command(self, ctype: int, target: int, duration: int) -> None:
        r = self.server.regs
        name = TYPES.get(ctype)
        if name is None:
            status, code = 2, 9
        elif name == "reset_alarm":
            status, code = 1, 0  # the app resets its own alarms; the sim latches nothing extra
        else:
            zid = self.zone_by_index.get(target) if name in ("start_zone", "stop_zone") else None
            if name in ("start_zone", "stop_zone") and zid is None:
                status, code = 2, 8
            elif name == "stop_zone" and self.engine.state.zones[zid].panel_mode != "auto":
                status, code = 2, 2
            else:
                cmd = {"id": f"vplc-{self._seq}", "command_type": name, "target_id": zid or ""}
                if name == "start_zone":
                    cmd["payload"] = {"duration_min": duration}
                res = self.engine.process_commands([cmd])[0]
                ok = res["status"] in ("accepted", "completed")
                status, code = (1, 0) if ok else (2, reason_code(res.get("failure_reason")))
        r[305], r[306] = status, code
        r[304] = self._seq  # last, like the PLC

    def _fallback_runs(self) -> list[dict]:
        r, today = self.server.regs, self.engine.sim_time
        runs = []
        for k in range(min(r[319], 20)):
            b = 320 + 4 * k
            zid = self.zone_by_index.get(r[b])
            if zid is None:
                continue
            days = (r[b + 3] - pc.dtl_weekday(today)) % 7
            day = (today + timedelta(days=days)).date()
            start = datetime(
                day.year, day.month, day.day, r[b + 1] // 60, r[b + 1] % 60, tzinfo=today.tzinfo
            )
            runs.append(
                {
                    "program_id": "plc",
                    "step_order": k,
                    "zone_id": zid,
                    "scheduled_start_farm": start.isoformat(),
                    "duration_min": r[b + 2],
                }
            )
        return runs

    def _outputs(self) -> None:
        s, r = self.engine.state, self.server.regs
        sysm = s.system
        r[0] = MODE_CODES.get(sysm.system_mode, 1)
        r[1], r[2], r[3] = int(sysm.estop), int(sysm.power_ok), int(sysm.fallback_active)
        r[4], r[5], r[6] = (
            _w(sysm.tank_level_pct, 10),
            _w(sysm.main_pressure_bar, 100),
            _w(sysm.main_flow_m3h, 100),
        )
        r[7], r[8] = _w(sysm.well_level_m, 100), _w(sysm.filter_dp_bar, 100)
        r[9] = (r[9] + 1) % 30000
        r[13], r[14] = 1, int(sysm.refilling)

        bits: set[int] = set()
        for cond in s.alarms.values():
            try:
                n = int(cond.code.split("-")[1])
            except (IndexError, ValueError):
                continue
            if cond.zone_id is None and 1 <= n <= 48:
                bits.add(n)
        words = [0, 0, 0]
        for n in bits:
            words[(n - 1) // 16] |= 1 << ((n - 1) % 16)
        r[10], r[11], r[12] = words

        valves = {v.zone_id: v for v in s.valves.values()}
        for idx, zid in self.zone_by_index.items():
            z = s.zones.get(zid)
            if z is None:
                continue
            b = 100 + 10 * (idx - 1)
            state = STATE_CODES.get(z.state, 0)
            fault = 0  # the zone's live alarm condition, like FB_Zone.AlarmCode
            for cond in s.alarms.values():
                if cond.zone_id == zid:
                    try:
                        fault = int(cond.code.split("-")[1])
                    except (IndexError, ValueError):
                        continue
                    break
            v = valves.get(zid)
            r[b] = int(z.state in ("validating_flow", "running", "warning"))
            r[b + 1] = int(v is not None and v.status == "open")
            r[b + 2], r[b + 3], r[b + 4] = (
                _w(z.flow_m3h, 100),
                _w(z.pressure_bar, 100),
                _w(z.moisture_pct, 10),
            )
            r[b + 5] = PANEL_ZONE_CODES.get(z.panel_mode, 0)
            r[b + 6] = state + 256 * SOURCE_CODES.get(z.run_source or "app", 0)
            r[b + 7], r[b + 8], r[b + 9] = (
                _w(z.runtime_sec),  # seconds, so the app's timer runs smoothly
                _w(z.target_runtime_sec),
                fault,
            )

        for pid, base in (("pump_booster_01", 270), ("pump_well_01", 280)):
            p = s.pumps.get(pid)
            if p is None:
                continue
            r[base], r[base + 1] = int(p.run_fb), int(p.fault or p.state == "failed_start")
            r[base + 2], r[base + 3] = _w(p.runtime_hours), PANEL_PUMP_CODES.get(p.panel_mode, 0)
            r[base + 4], r[base + 5], r[base + 6] = (
                _w(p.power_kw, 100),
                _w(p.current_a, 10),
                _w(p.energy_kwh_today, 10),
            )


class VirtualPlantGateway(ModbusAdapter):
    """The production Modbus adapter, plus a direct line to the simulated farm for
    simulation-only commands and the field sensors (which reach the app without the PLC)."""

    name = "modbus"

    def __init__(self, regmap: dict, engine: SimulatorEngine, **kw):
        super().__init__(regmap, **kw)
        self.engine = engine

    async def execute(self, commands: list[dict]) -> list[dict]:
        plant = [c for c in commands if c.get("command_type") in SIM_ONLY]
        plc = [c for c in commands if c.get("command_type") not in SIM_ONLY]
        out = self.engine.process_commands(plant) if plant else []
        return out + (await super().execute(plc) if plc else [])

    async def read_state(self) -> list[dict]:
        out = await super().read_state()
        if out:
            sensors = [
                p
                for p in self.engine.state.get_sync_payloads()
                if p["device_key"].startswith("sensor_")
            ]
            out.extend(sensors)
        return out

    def link_ok(self) -> bool:
        """The Simulator page's 'comms drop' cuts the PLC <-> server link (as a real outage would)."""
        until = self.engine.state.faults.comms_drop_until
        if until is not None and utcnow() < until:
            return False
        return super().link_ok()
