"""The farm around the REAL PLC program running in PLCSIM Advanced (G5).

The PLC program (plc/src) decides everything; this module only plays the field:
  - reads the PLC's outputs (valve DQ bytes, pump starts),
  - turns them into pump feedback, flow, pressure, tank and well levels,
  - writes those back as the PLC's inputs (digital inputs and 4-20 mA raw values).
It talks to PLCSIM through tools/plcsim/PlcsimBridge.exe (PLCSIM Advanced API, no extra package).

The app reaches the PLC as on the farm: CONTROLLER_ADAPTER=modbus to the instance's IP. The
Simulator page's switches and faults go to this farm model (PlcsimGateway), like PLCSIM inputs.

    CONTROLLER_ADAPTER=modbus PLCSIM_PLANT=1 MODBUS_HOST=192.168.0.1 python -m src.main
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .adapters.modbus_adapter import ModbusAdapter
from .state import utcnow

ROOT = Path(__file__).resolve().parents[3]
BRIDGE_EXE = ROOT / "tools" / "plcsim" / "PlcsimBridge.exe"
RAW_FULL = 27648  # ET 200SP AI: 20 mA
# analog ranges = DB_Config start values (TankLevelMaxPct ... FilterDpMaxBar)
RANGE = {"tank": 100.0, "pressure": 10.0, "flow": 50.0, "well": 30.0, "filter": 2.5}
SIM_ONLY = {"set_panel", "inject_fault", "set_mode"}
MODE_CODES = {"off": 0, "auto": 1, "manual": 2, "maintenance": 3}


class BridgeClient:
    """Line protocol to PlcsimBridge.exe (see its header)."""

    def __init__(self, port: int = 1600):
        self.port = port
        self._r: asyncio.StreamReader | None = None
        self._w: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._r, self._w = await asyncio.open_connection("127.0.0.1", self.port)

    async def ask(self, line: str) -> str:
        async with self._lock:
            if self._w is None:
                await self.connect()
            self._w.write((line + "\n").encode("ascii"))
            await self._w.drain()
            answer = (await asyncio.wait_for(self._r.readline(), 5)).decode("ascii").strip()
        if answer.startswith("ERR"):
            raise RuntimeError(answer)
        return answer

    async def batch(self, ops: list[str]) -> list[str]:
        return (await self.ask("X " + "|".join(ops))).split("|")

    async def close(self) -> None:
        if self._w is not None:
            self._w.close()
        self._r = self._w = None


@dataclass
class Plant:
    zone_index: dict[str, int]  # zone id -> PLC index (1..16)
    zone_flow: float = 4.0  # m3/h per open zone
    tank_m3: float = 50.0
    tank_pct: float = 70.0
    well_m: float = 12.0
    filter_dp: float = 0.08
    # field state
    booster_run: bool = False
    well_run: bool = False
    booster_t: float = 0.0
    well_t: float = 0.0
    # faults and switches (set from the Simulator page)
    estop: bool = False
    mains_off: bool = False
    leak: bool = False
    well_low: bool = False
    filter_clog: bool = False
    tank_sensor_broken: bool = False  # a cut wire: the analog input reads overflow
    well_sensor_broken: bool = False
    pump_trip: set[str] = field(default_factory=set)
    pump_fail_start: set[str] = field(default_factory=set)
    valve_stuck_closed: set[str] = field(default_factory=set)
    valve_hand_open: set[str] = field(default_factory=set)
    valve_stuck_open: set[str] = field(default_factory=set)  # commanded closed, stays open
    zone_blocked: set[str] = field(default_factory=set)
    zone_panel: dict[str, str] = field(default_factory=dict)  # zone id -> on | off
    pump_panel: dict[str, str] = field(default_factory=dict)  # pump id -> hand | off
    comms_drop_until: object = None
    # last values (for tests / logs)
    main_flow: float = 0.0
    main_pressure: float = 0.0

    # ── one step (dt seconds of real time; the PLC runs on real time) ──

    def step(
        self, dt: float, valve_lo: int, valve_hi: int, booster_cmd: bool, well_cmd: bool
    ) -> None:
        open_zones = []
        for zid, idx in self.zone_index.items():
            bits = valve_lo if idx <= 8 else valve_hi
            commanded = bool((bits >> ((idx - 1) % 8)) & 1)
            valve = "valve_" + zid.removeprefix("zone_")
            is_open = (
                (commanded and valve not in self.valve_stuck_closed)
                or valve in self.valve_hand_open
                or valve in self.valve_stuck_open
            )
            if is_open and zid not in self.zone_blocked:
                open_zones.append(zid)

        powered = not self.mains_off
        self.booster_run, self.booster_t = self._pump(
            "pump_booster_01", booster_cmd and powered, self.booster_run, self.booster_t, dt
        )
        self.well_run, self.well_t = self._pump(
            "pump_well_01",
            well_cmd and powered and self.well_m > 1.0,
            self.well_run,
            self.well_t,
            dt,
        )

        # The PLC picks the source: booster from the tank, or straight from the well when the tank
        # is critical (then only the well pump runs). Open zones take water from whichever runs.
        from_tank = self.booster_run and self.tank_pct > 0.5
        from_well = self.well_run and not self.booster_run
        tank_zones = open_zones if from_tank else []
        flow = self.zone_flow * len(open_zones) if (from_tank or from_well) else 0.0
        if self.leak and (from_tank or from_well):
            flow += 6.0
        self.main_flow = flow
        if flow > 0:
            self.main_pressure = max(0.6, 2.8 - 0.05 * flow - (1.2 if self.leak else 0.0))
        elif self.booster_run:
            self.main_pressure = 3.8  # dead-headed against closed valves
        else:
            self.main_pressure = 0.0

        # tank: well refills, booster draws
        refill = 8.0 if self.well_run else 0.0
        draw = (
            self.zone_flow * len(tank_zones) + (6.0 if self.leak else 0.0)
            if self.booster_run
            else 0.0
        )
        self.tank_pct = min(
            100.0, max(0.0, self.tank_pct + (refill - draw) * dt / 3600.0 / self.tank_m3 * 100.0)
        )
        target_well = (1.0 if self.well_low else 12.0) - (3.0 if self.well_run else 0.0)
        self.well_m += (target_well - self.well_m) * min(1.0, dt / 20.0)
        target_dp = (0.9 if self.filter_clog else 0.08) + 0.01 * flow
        self.filter_dp += (target_dp - self.filter_dp) * min(1.0, dt / 10.0)

    def _pump(self, pid, cmd, run, t, dt):
        if pid in self.pump_trip or not cmd or pid in self.pump_fail_start:
            return False, 0.0
        t += dt
        return t >= 1.5, t  # run feedback 1.5 s after the start command

    # ── PLC inputs ──

    def inputs(self) -> list[str]:
        def raw(v, full):
            return str(int(max(0.0, min(1.0, v / full)) * RAW_FULL))

        on_lo = on_hi = off_lo = off_hi = 0
        for zid, pos in self.zone_panel.items():
            idx = self.zone_index.get(zid)
            if not idx:
                continue
            bit = 1 << ((idx - 1) % 8)
            if pos == "on":
                on_lo, on_hi = (on_lo | bit, on_hi) if idx <= 8 else (on_lo, on_hi | bit)
            elif pos == "off":
                off_lo, off_hi = (off_lo | bit, off_hi) if idx <= 8 else (off_lo, off_hi | bit)
        b = lambda v: "1" if v else "0"  # noqa: E731
        bp, wp = self.pump_panel.get("pump_booster_01"), self.pump_panel.get("pump_well_01")
        return [
            f"W DI_EStopOk bool {b(not self.estop)}",
            f"W DI_MainsOk bool {b(not self.mains_off)}",
            f"W DI_BoosterRun bool {b(self.booster_run)}",
            f"W DI_BoosterFault bool {b('pump_booster_01' in self.pump_trip)}",
            f"W DI_WellRun bool {b(self.well_run)}",
            f"W DI_WellFault bool {b('pump_well_01' in self.pump_trip)}",
            f"W DI_BoosterHand bool {b(bp == 'hand')}",
            f"W DI_BoosterOff bool {b(bp == 'off')}",
            f"W DI_WellHand bool {b(wp == 'hand')}",
            f"W DI_WellOff bool {b(wp == 'off')}",
            f"W DI_ZoneOnLo u8 {on_lo}",
            f"W DI_ZoneOnHi u8 {on_hi}",
            f"W DI_ZoneOffLo u8 {off_lo}",
            f"W DI_ZoneOffHi u8 {off_hi}",
            "W AI_TankLevel i16 "
            + ("32767" if self.tank_sensor_broken else raw(self.tank_pct, RANGE["tank"])),
            f"W AI_MainPressure i16 {raw(self.main_pressure, RANGE['pressure'])}",
            f"W AI_MainFlow i16 {raw(self.main_flow, RANGE['flow'])}",
            "W AI_WellLevel i16 "
            + ("32767" if self.well_sensor_broken else raw(self.well_m, RANGE["well"])),
            f"W AI_FilterDp i16 {raw(self.filter_dp, RANGE['filter'])}",
        ]

    # ── Simulator page ──

    def apply(self, ctype: str, target: str | None, payload: dict) -> tuple[bool, str | None]:
        if ctype == "set_panel":
            kind, pos = payload.get("kind"), payload.get("position")
            tid = target or payload.get("id") or ""
            book = self.zone_panel if kind == "zone" else self.pump_panel
            if pos in (None, "auto"):
                book.pop(tid, None)
            else:
                book[tid] = pos
            return True, None
        if ctype != "inject_fault":
            return False, f"unsupported {ctype}"
        tt, tid, ft, value = (
            payload.get("target_type"),
            payload.get("target_id"),
            payload.get("fault_type"),
            payload.get("value"),
        )
        if tt == "pump":
            for s in (self.pump_trip, self.pump_fail_start):
                s.discard(tid)
            if ft == "trip":
                self.pump_trip.add(tid)
            elif ft == "fail_start":
                self.pump_fail_start.add(tid)
        elif tt == "valve":
            for s in (self.valve_stuck_closed, self.valve_hand_open, self.valve_stuck_open):
                s.discard(tid)
            if ft == "stuck_open":
                self.valve_stuck_open.add(tid)
            elif ft == "stuck_closed":
                self.valve_stuck_closed.add(tid)
            elif ft == "hand_open":
                self.valve_hand_open.add(tid)
        elif tt == "zone":
            self.zone_blocked.discard(tid)
            if ft == "blocked":
                self.zone_blocked.add(tid)
        elif tt == "tank" and ft == "set_level" and value is not None:
            self.tank_pct = float(value)
        elif tt == "comms" and ft == "drop":
            from datetime import timedelta

            self.comms_drop_until = utcnow() + timedelta(seconds=float(value or 45))
        elif tt == "system":
            flags = {
                "mainline_leak": ("leak", True),
                "clear_leak": ("leak", False),
                "estop": ("estop", True),
                "estop_release": ("estop", False),
                "power_cut": ("mains_off", True),
                "power_restore": ("mains_off", False),
                "well_low": ("well_low", True),
                "well_recover": ("well_low", False),
                "filter_clog": ("filter_clog", True),
                "filter_clean": ("filter_clog", False),
                "tank_sensor_break": ("tank_sensor_broken", True),
                "tank_sensor_repair": ("tank_sensor_broken", False),
                "well_sensor_break": ("well_sensor_broken", True),
                "well_sensor_repair": ("well_sensor_broken", False),
            }
            if ft == "clear_all":
                for attr, _ in flags.values():
                    setattr(self, attr, False)
                for s in (
                    self.pump_trip,
                    self.pump_fail_start,
                    self.valve_stuck_closed,
                    self.valve_hand_open,
                    self.valve_stuck_open,
                    self.zone_blocked,
                ):
                    s.clear()
                self.zone_panel.clear()
                self.pump_panel.clear()
            elif ft in flags:
                setattr(self, *flags[ft])
            else:
                return False, f"unknown system fault {ft}"
        else:
            return False, f"unsupported fault {tt}/{ft}"
        return True, None


class PlantRunner:
    """Exchanges the PLC's I/O with the farm model every period."""

    def __init__(self, plant: Plant, bridge: BridgeClient, period: float = 0.2):
        self.plant, self.bridge, self.period = plant, bridge, period
        self.running = False
        self.mode_request: int | None = None

    async def tick(self) -> None:
        out = await self.bridge.batch(
            ["R DQ_ValveLo u8", "R DQ_ValveHi u8", "R DQ_BoosterStart bool", "R DQ_WellStart bool"]
        )
        self.plant.step(self.period, int(out[0]), int(out[1]), out[2] == "1", out[3] == "1")
        ops = self.plant.inputs()
        if self.mode_request is not None:
            ops.append(f"W DB_Farm.Mode i16 {self.mode_request}")
            self.mode_request = None
        await self.bridge.batch(ops)

    async def run(self) -> None:
        self.running = True
        print("[PLANT] Farm model driving the PLCSIM PLC")
        while self.running:
            try:
                await self.tick()
            except Exception as exc:  # PLC stopped / being downloaded: keep trying
                print(f"[PLANT] {type(exc).__name__}: {exc}")
                await self.bridge.close()
                await asyncio.sleep(2.0)
            await asyncio.sleep(self.period)


class PlcsimGateway(ModbusAdapter):
    """The production Modbus adapter to the PLC, plus the Simulator page's buttons to the farm."""

    def __init__(self, regmap: dict, runner: PlantRunner, **kw):
        super().__init__(regmap, **kw)
        self.runner = runner

    async def execute(self, commands: list[dict]) -> list[dict]:
        out = []
        plc = []
        for c in commands:
            if c.get("command_type") not in SIM_ONLY:
                plc.append(c)
                continue
            payload = c.get("payload") or {}
            if isinstance(payload, str):
                import json

                payload = json.loads(payload)
            if c["command_type"] == "set_mode":
                self.runner.mode_request = MODE_CODES.get(payload.get("mode", "auto"), 1)
                ok, reason = True, None
            else:
                ok, reason = self.runner.plant.apply(c["command_type"], c.get("target_id"), payload)
            res = {
                "command_id": c.get("id") or c.get("command_id"),
                "status": "completed" if ok else "failed",
            }
            if reason:
                res["failure_reason"] = reason
            out.append(res)
        return out + (await super().execute(plc) if plc else [])

    def link_ok(self) -> bool:
        until = self.runner.plant.comms_drop_until
        if until is not None and utcnow() < until:
            return False
        return super().link_ok()


def start_bridge(instance: str, port: int) -> subprocess.Popen | None:
    if not BRIDGE_EXE.exists():
        raise SystemExit(f"{BRIDGE_EXE} is missing: build it (see tools/plcsim/PlcsimBridge.cs)")
    return subprocess.Popen(
        [str(BRIDGE_EXE), instance, str(port)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def plant_from_env(regmap: dict) -> tuple[Plant, PlantRunner, subprocess.Popen | None]:
    port = int(os.getenv("PLCSIM_BRIDGE_PORT", "1600"))
    proc = start_bridge(os.getenv("PLCSIM_INSTANCE", "PLC"), port)
    zone_index = {zid: int(z["index"]) for zid, z in regmap["zones"].items() if "index" in z}
    plant = Plant(zone_index=zone_index)
    return plant, PlantRunner(plant, BridgeClient(port)), proc
