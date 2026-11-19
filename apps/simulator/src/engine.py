"""
Deterministic farm simulator — plays the role of the PLC *and* the physical farm.

PLC part (control): timed zone start/stop sequences from PLC_CONTROL_LOGIC.md §3,
pump start supervision, valve travel supervision, flow validation, leak / low-tank /
e-stop protection. Protection conditions are reported to the backend as
`plc_alarms`; the backend owns the alarm lifecycle (ack/reset/history).

Physics part (world): pump curves, emitter flow ~ sqrt(pressure), mainline leak,
tank mass balance with well refill, soil moisture wetting/drying, sensor noise.
Constants live in `Hydraulics` until real site data exists.
"""

import asyncio
import json
import math
import random
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from .faults import FaultInjector
from .state import AlarmCondition, FarmSimulationState, SimZoneState, utcnow

ACTIVE_STATES = {"starting_pump", "opening_valve", "validating_flow", "running", "stopping"}
PUMP_ALARMS = {"booster": ("ALM-005", "ALM-006"), "well": ("ALM-004", "ALM-007")}
TRIPOLI_UTC_OFFSET_H = 2


class SimulatorEngine:
    def __init__(self, state: FarmSimulationState, timescale: float = 1.0, seed: int = 42):
        self.state = state
        self.timescale = timescale
        self.paused = False
        self.running = False
        self.rng = random.Random(seed)
        self.faults = FaultInjector(self)
        self.sim_time = utcnow()
        # per-zone controller memory
        self.phase_t: dict[str, float] = {}  # seconds spent in current phase
        self.zone_cmd: dict[str, str] = {}  # start command awaiting running/failed
        self.zone_abort: dict[str, tuple[str, str]] = {}  # zone → (alarm code, reason)
        self.pump_t: dict[str, float] = {}
        self.pump_lock: set[str] = set()  # pumps the PLC holds off (isolation)
        self.leak_t = 0.0
        self.true_tank_pct = state.system.tank_level_pct
        self.outbox: list[dict] = []  # command updates to send to the API

    # ── Commands ─────────────────────────────────────────

    def process_commands(self, commands: list[dict]) -> list[dict]:
        """Execute commands from the API; returns immediate status updates."""
        updates = []
        for cmd in commands:
            ctype, tid, cid = cmd.get("command_type"), cmd.get("target_id"), cmd.get("id")
            payload = cmd.get("payload") or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            try:
                status, reason = self._execute(ctype, tid, payload, cid)
            except Exception as e:  # never let one bad command kill the loop
                status, reason = "failed", str(e)
            updates.append(self._update(cid, status, reason))
        return updates

    def _execute(self, ctype, tid, payload, cid) -> tuple[str, str | None]:
        s = self.state
        if ctype == "start_zone":
            return self.start_zone(tid, payload.get("duration_min"), cid)
        if ctype == "stop_zone":
            if tid not in s.zones:
                return "failed", f"Zone {tid} not found"
            self.begin_stop(tid)
            return "completed", None
        if ctype == "stop_all":
            for zid in s.zones:
                self.begin_stop(zid)
            return "completed", None
        if ctype == "set_mode":
            s.system.system_mode = payload.get("mode", "auto")
            return "completed", None
        if ctype == "inject_fault":
            ok, msg = self.faults.handle(payload)
            return ("completed", None) if ok else ("failed", msg)
        return "rejected", f"Unsupported command {ctype}"

    @staticmethod
    def _update(cid, status, reason=None) -> dict:
        return {
            "command_id": cid,
            "status": status,
            "failure_reason": reason,
        }

    def drain_outbox(self) -> list[dict]:
        out, self.outbox = self.outbox, []
        return out

    # ── Zone sequences ───────────────────────────────────

    def start_zone(self, zid, duration_min, cid=None) -> tuple[str, str | None]:
        s, h = self.state, self.state.hyd
        z, cfg = s.zones.get(zid), s.zone_cfg.get(zid)
        if not z or not cfg:
            return "failed", f"Zone {zid} not found"
        if s.system.estop:
            return "failed", "Emergency stop is active"
        if z.state in ACTIVE_STATES:
            return "failed", f"Zone {cfg.code} is already active"
        use_well = cfg.allows_direct_well and s.system.tank_level_pct < h.tank_warning_pct
        source = "well_direct" if use_well else "tank"
        if source == "tank" and s.system.tank_level_pct < h.tank_critical_pct:
            return "failed", "Tank critically low"
        pump = s.pump_of_type("well" if use_well else "booster")
        if not pump or pump.fault or pump.state == "failed_start":
            return "failed", f"{'Well' if use_well else 'Booster'} pump unavailable"
        minutes = duration_min or cfg.default_duration_min
        minutes = max(1, min(int(minutes), cfg.max_runtime_min))
        z.state, z.health, z.source_mode = "starting_pump", "healthy", source
        z.runtime_sec, z.target_runtime_sec = 0, minutes * 60
        self.phase_t[zid] = 0.0
        self.zone_abort.pop(zid, None)
        if cid:
            self.zone_cmd[zid] = cid
            return "accepted", None
        return "completed", None

    def begin_stop(self, zid: str) -> None:
        z = self.state.zones.get(zid)
        if z and z.state in ACTIVE_STATES and z.state != "stopping":
            z.state = "stopping"
            self.phase_t[zid] = 0.0
            self._valve_command(zid, "close")
            if zid in self.zone_cmd:  # stopped before it reached running
                self._finish_cmd(zid, "failed", "Stopped before the zone was running")

    def abort_zone(self, zid: str, code: str | None, reason: str) -> None:
        z = self.state.zones[zid]
        if z.state not in ACTIVE_STATES:
            return
        self.zone_abort[zid] = (code or "", reason)
        z.health = "critical"
        if z.state == "stopping":
            return
        z.state = "stopping"
        self.phase_t[zid] = 0.0
        self._valve_command(zid, "close")
        self._finish_cmd(zid, "failed", reason)

    def _finish_cmd(self, zid: str, status: str, reason: str | None = None) -> None:
        cid = self.zone_cmd.pop(zid, None)
        if cid:
            self.outbox.append(self._update(cid, status, reason))

    def _valve_command(self, zid: str, cmd: str) -> None:
        v = self.state.valve_for_zone(zid)
        if v and v.last_command != cmd:
            v.last_command = cmd
            self.phase_t[f"valve:{v.valve_id}"] = 0.0

    def _zone_pump(self, z: SimZoneState):
        return self.state.pump_of_type("well" if z.source_mode == "well_direct" else "booster")

    def _step_zone(self, zid: str, dt: float) -> None:
        s, h = self.state, self.state.hyd
        z, cfg = s.zones[zid], s.zone_cfg.get(zid)
        if cfg is None or z.state not in ACTIVE_STATES:
            return
        self.phase_t[zid] = self.phase_t.get(zid, 0.0) + dt
        t = self.phase_t[zid]
        valve = s.valve_for_zone(zid)
        pump = self._zone_pump(z)

        if z.state == "starting_pump":
            if pump and pump.state == "running":
                z.state, self.phase_t[zid] = "opening_valve", 0.0
                self._valve_command(zid, "open")
            elif pump and pump.state in ("failed_start", "faulted"):
                self.abort_zone(zid, None, "Pump failed to start")
        elif z.state == "opening_valve":
            if valve is None or valve.status == "open":
                z.state, self.phase_t[zid] = "validating_flow", 0.0
            elif t >= h.valve_timeout_s:
                valve.status = "fault"
                s.raise_alarm(
                    AlarmCondition(
                        "ALM-019", zone_id=zid, device_id=valve.valve_id, detail="no open feedback"
                    )
                )
                self.abort_zone(zid, "ALM-019", "Valve failed to open")
        elif z.state == "validating_flow":
            if z.flow_m3h >= cfg.flow_min_m3h * 0.8:
                z.state, self.phase_t[zid] = "running", 0.0
                self._finish_cmd(zid, "completed")
            elif t >= h.flow_validation_s:
                s.raise_alarm(
                    AlarmCondition(
                        "ALM-012",
                        zone_id=zid,
                        value=round(z.flow_m3h, 2),
                        threshold=cfg.flow_min_m3h,
                    )
                )
                self.abort_zone(zid, "ALM-012", "No flow after valve opened")
        elif z.state == "running":
            z.runtime_sec += dt
            if z.runtime_sec >= z.target_runtime_sec:
                self.begin_stop(zid)
        elif z.state == "stopping":
            stuck_open = valve is not None and valve.valve_id in s.faults.valve_stuck_open
            closed = (
                valve is None
                or valve.status == "closed"
                or (valve.status == "fault" and not stuck_open)
            )
            if closed:
                z.state = "faulted" if zid in self.zone_abort else "completed"
                if z.state == "completed":
                    z.health = "healthy"
                self.phase_t[zid] = 0.0
            elif t >= h.valve_timeout_s and valve.status != "fault":
                valve.status = "fault"  # stuck open: PLC isolates by stopping the pump
                s.raise_alarm(AlarmCondition("ALM-020", zone_id=zid, device_id=valve.valve_id))
                self.zone_abort[zid] = ("ALM-020", "Valve failed to close")
                z.state, z.health = "faulted", "critical"
                if pump:
                    self.pump_lock.add(pump.pump_id)

    # ── Pumps & valves ───────────────────────────────────

    def _pump_demand(self, pump) -> bool:
        s = self.state
        if pump.pump_type == "well" and s.system.refilling:
            return True
        source = "well_direct" if pump.pump_type == "well" else "tank"
        if pump.pump_id in self.pump_lock:
            return False
        return any(z.state in ACTIVE_STATES and z.source_mode == source for z in s.zones.values())

    def _step_pumps(self, dt: float) -> None:
        s, h = self.state, self.state.hyd
        for p in s.pumps.values():
            trip_code, fail_code = PUMP_ALARMS.get(p.pump_type, ("ALM-005", "ALM-006"))
            if p.pump_id in s.faults.pump_trip:
                if not p.fault:
                    p.state, p.fault, p.run_fb = "faulted", True, False
                    s.raise_alarm(AlarmCondition(trip_code, device_id=p.pump_id))
                    self._abort_dependents(p, trip_code, "Pump tripped")
                continue
            if p.fault:  # trip repaired
                p.state, p.fault = "stopped", False
                s.clear_alarm(trip_code, p.pump_id)
            if p.state == "failed_start":
                if p.pump_id not in s.faults.pump_fail_start:
                    p.state = "stopped"
                    s.clear_alarm(fail_code, p.pump_id)
                continue

            demand = self._pump_demand(p) and not s.system.estop
            if not demand:
                if p.state in ("starting", "running"):
                    p.state, p.run_fb = "stopped", False
                continue
            if p.state in ("stopped", "cooldown"):
                p.state, self.pump_t[p.pump_id] = "starting", 0.0
                p.starts_today += 1
            elif p.state == "starting":
                self.pump_t[p.pump_id] = self.pump_t.get(p.pump_id, 0.0) + dt
                t = self.pump_t[p.pump_id]
                if p.pump_id in s.faults.pump_fail_start:
                    if t >= h.pump_start_timeout_s:
                        p.state = "failed_start"
                        s.raise_alarm(AlarmCondition(fail_code, device_id=p.pump_id))
                        self._abort_dependents(p, fail_code, "Pump failed to start")
                elif t >= h.pump_start_s:
                    p.state, p.run_fb = "running", True
            elif p.state == "running":
                p.runtime_hours += dt / 3600.0

    def _abort_dependents(self, pump, code: str, reason: str) -> None:
        source = "well_direct" if pump.pump_type == "well" else "tank"
        for zid, z in self.state.zones.items():
            if z.state in ACTIVE_STATES and z.source_mode == source:
                self.abort_zone(zid, code, reason)

    def _step_valves(self, dt: float) -> None:
        s, h = self.state, self.state.hyd
        for v in s.valves.values():
            if v.status == "fault":
                continue
            key = f"valve:{v.valve_id}"
            self.phase_t[key] = self.phase_t.get(key, 0.0) + dt
            if v.last_command == "open" and v.status != "open":
                if v.valve_id in s.faults.valve_stuck_closed:
                    v.status = "closed"
                else:
                    v.status = "open" if self.phase_t[key] >= h.valve_travel_s else "opening"
            elif v.last_command == "close" and v.status != "closed":
                if v.valve_id in s.faults.valve_stuck_open:
                    v.status = "open"
                else:
                    v.status = "closed" if self.phase_t[key] >= h.valve_travel_s else "closing"

    def _valve_fraction(self, zid: str) -> float:
        v = self.state.valve_for_zone(zid)
        if v is None:
            return 1.0 if self.state.zones[zid].state in ACTIVE_STATES else 0.0
        if v.status == "fault":
            return 1.0 if v.valve_id in self.state.faults.valve_stuck_open else 0.0
        if v.status == "open":
            return 1.0
        if v.status in ("opening", "closing"):
            frac = min(
                1.0, self.phase_t.get(f"valve:{v.valve_id}", 0.0) / self.state.hyd.valve_travel_s
            )
            return frac if v.status == "opening" else 1.0 - frac
        return 0.0

    # ── Hydraulics ───────────────────────────────────────

    def _solve_path(
        self, pump, zone_ids, setpoint, shutoff, k, leak: bool
    ) -> tuple[float, dict[str, float]]:
        """Fixed-point solve of regulated pump curve vs emitters (+ optional leak)."""
        h = self.state.hyd
        running = pump is not None and pump.state == "running"
        if not running:
            return 0.0, dict.fromkeys(zone_ids, 0.0)
        p = setpoint
        flows: dict[str, float] = {}
        for _ in range(25):
            ratio = math.sqrt(max(p, 0.0) / h.nominal_pressure_bar)
            flows = {}
            for zid in zone_ids:
                cfg = self.state.zone_cfg[zid]
                blocked = zid in self.state.faults.zone_blocked
                flows[zid] = (
                    0.0 if blocked else cfg.nominal_flow_m3h * self._valve_fraction(zid) * ratio
                )
            total = sum(flows.values()) + (h.leak_flow_at_nominal_m3h * ratio if leak else 0.0)
            p_new = max(0.0, min(setpoint, shutoff - k * total * total))
            p = 0.5 * p + 0.5 * p_new
        return p, flows

    def _step_hydraulics(self, dt: float) -> None:
        s, h = self.state, self.state.hyd
        booster, well = s.pump_of_type("booster"), s.pump_of_type("well")
        tank_zones = [
            z for z, st in s.zones.items() if st.source_mode != "well_direct" and z in s.zone_cfg
        ]
        well_zones = [
            z for z, st in s.zones.items() if st.source_mode == "well_direct" and z in s.zone_cfg
        ]

        leak = s.faults.mainline_leak
        p_main, tank_flows = self._solve_path(
            booster, tank_zones, h.booster_setpoint_bar, h.booster_shutoff_bar, h.booster_k, leak
        )
        p_well, well_flows = self._solve_path(
            well, well_zones, h.well_setpoint_bar, h.well_shutoff_bar, h.well_k, False
        )

        alpha = 1.0 - math.exp(-dt / h.pump_tau_s)
        s.system.main_pressure_bar += (p_main - s.system.main_pressure_bar) * alpha
        main_ratio = math.sqrt(s.system.main_pressure_bar / p_main) if p_main > 0.01 else 0.0
        leak_flow = (
            h.leak_flow_at_nominal_m3h
            * math.sqrt(s.system.main_pressure_bar / h.nominal_pressure_bar)
            if leak and booster and booster.state == "running"
            else 0.0
        )
        main_flow = leak_flow
        for zid, q in tank_flows.items():
            z = s.zones[zid]
            z.flow_m3h = q * main_ratio
            z.pressure_bar = max(0.0, s.system.main_pressure_bar - 0.2) if z.flow_m3h > 0 else 0.0
            main_flow += z.flow_m3h
        for zid, q in well_flows.items():
            z = s.zones[zid]
            z.flow_m3h = q
            z.pressure_bar = max(0.0, p_well - 0.2) if q > 0 else 0.0
        s.system.main_flow_m3h = main_flow

        # leak detection (PLC): compare the mainline meter with what the open zones'
        # emitters should pass at the current pressure (commissioned nominal flow).
        # A fixed "max flow" band is too loose for large zones — a leak hides inside it.
        p_ratio = math.sqrt(max(s.system.main_pressure_bar, 0.0) / h.nominal_pressure_bar)
        expected = sum(
            s.zone_cfg[z].nominal_flow_m3h * self._valve_fraction(z) * p_ratio
            for z in tank_zones
            if z not in s.faults.zone_blocked
        )
        limit = max(expected * 1.25, expected + 2.0)
        if expected > 0 and main_flow > limit:
            self.leak_t += dt
            if self.leak_t >= h.leak_detect_s and "ALM-013:system" not in s.alarms:
                s.raise_alarm(
                    AlarmCondition(
                        "ALM-013",
                        value=round(main_flow, 2),
                        threshold=round(limit, 2),
                    )
                )
                for zid in tank_zones:
                    self.abort_zone(zid, "ALM-013", "Abnormal high flow — leak suspected")
        else:
            self.leak_t = 0.0
        if not leak:
            s.clear_alarm("ALM-013")

        # tank mass balance + refill control (uses the *reported* level, like a real PLC)
        refill = 0.0
        if well and well.state == "running" and not any(well_flows.values()):
            refill = h.well_refill_flow_m3h
        tank_out = sum(tank_flows.values()) * main_ratio + leak_flow
        self.true_tank_pct += (refill - tank_out) * dt / 3600.0 / h.tank_capacity_m3 * 100.0
        self.true_tank_pct = min(100.0, max(0.0, self.true_tank_pct))
        if not s.faults.tank_sensor_fault:
            s.system.tank_level_pct = self.true_tank_pct
        level = s.system.tank_level_pct
        if level < h.tank_refill_start_pct:
            s.system.refilling = True
        elif level >= h.tank_refill_stop_pct:
            s.system.refilling = False

    # ── Protection & environment ─────────────────────────

    def _step_protection(self) -> None:
        s, h = self.state, self.state.hyd
        if s.system.estop:
            s.raise_alarm(AlarmCondition("ALM-041", detail="emergency stop pressed"))
            for zid in s.zones:
                self.abort_zone(zid, "ALM-041", "Emergency stop")
        else:
            s.clear_alarm("ALM-041")

        level = s.system.tank_level_pct
        if level < h.tank_critical_pct:
            s.raise_alarm(
                AlarmCondition("ALM-002", value=round(level, 1), threshold=h.tank_critical_pct)
            )
            for zid, z in s.zones.items():
                if z.state in ACTIVE_STATES and z.source_mode == "tank":
                    self.abort_zone(zid, "ALM-002", "Tank critically low")
        elif level >= h.tank_critical_clear_pct:
            s.clear_alarm("ALM-002")

        if s.faults.tank_sensor_fault:
            s.raise_alarm(AlarmCondition("ALM-003", device_id="sensor_tank_level"))
        else:
            s.clear_alarm("ALM-003", "sensor_tank_level")

        # repaired valves/zones clear their PLC conditions
        for key in list(s.alarms):
            cond = s.alarms[key]
            if cond.code in ("ALM-019", "ALM-020") and cond.device_id:
                v = s.valves.get(cond.device_id)
                stuck = cond.device_id in (s.faults.valve_stuck_closed | s.faults.valve_stuck_open)
                if v and not stuck:
                    if v.status == "fault":
                        v.status = "closed" if cond.code == "ALM-019" else "closing"
                        self.phase_t[f"valve:{v.valve_id}"] = 0.0
                    s.alarms.pop(key)
                    if cond.code == "ALM-020":
                        pump = self._zone_pump(s.zones[cond.zone_id]) if cond.zone_id else None
                        if pump:
                            self.pump_lock.discard(pump.pump_id)
            elif cond.code == "ALM-012" and cond.zone_id not in s.faults.zone_blocked:
                s.alarms.pop(key)

    def _step_environment(self, dt: float) -> None:
        s = self.state
        tz = ZoneInfo("Africa/Tripoli")
        local = self.sim_time.astimezone(tz)
        local_hour = (local.hour + local.minute / 60.0 + local.second / 3600.0) % 24
        daylight = max(0.0, math.sin(math.pi * (local_hour - 6) / 12))
        dry_rate = 0.3 + 0.9 * daylight  # %/h evapotranspiration
        for zid, z in s.zones.items():
            cfg = s.zone_cfg.get(zid)
            wet_rate = 20.0 * (z.flow_m3h / cfg.nominal_flow_m3h) if cfg and z.flow_m3h > 0 else 0.0
            z.moisture_pct += (wet_rate - dry_rate) * dt / 3600.0
            z.moisture_pct = min(95.0, max(10.0, z.moisture_pct))
            z.active_alarm_count = sum(1 for a in s.alarms.values() if a.zone_id == zid)

    def _step_sensors(self) -> None:
        s, now = self.state, utcnow()
        for sensor in s.sensors.values():
            noise = self.rng.gauss(0, 1)
            if sensor.metric_key == "tank_level_pct":
                if s.faults.tank_sensor_fault:
                    sensor.quality = "bad"
                    sensor.timestamp = now
                    continue
                sensor.value = round(s.system.tank_level_pct + 0.1 * noise, 2)
            elif sensor.metric_key == "main_pressure_bar":
                sensor.value = round(max(0.0, s.system.main_pressure_bar + 0.02 * noise), 3)
            elif sensor.metric_key == "main_flow_m3h":
                sensor.value = round(max(0.0, s.system.main_flow_m3h + 0.05 * noise), 3)
            elif sensor.metric_key.startswith("moisture:"):
                z = s.zones.get(sensor.metric_key.split(":", 1)[1])
                if z:
                    sensor.value = round(z.moisture_pct + 0.3 * noise, 2)
            sensor.quality = "good"
            sensor.timestamp = now

    # ── Main step & Jump ─────────────────────────────────

    def manual_step(self, dt: float) -> None:
        """Advance physics and sim_time by dt seconds even if paused, without aborting zones."""
        if dt <= 0:
            return
        was_paused = self.paused
        self.paused = False
        try:
            n = max(1, math.ceil(dt / 2.0))
            for _ in range(n):
                self.step(dt / n)
        finally:
            self.paused = was_paused

    def jump(self, new_sim_time) -> None:
        """Monotonic jump: stop running zones, apply closed-form environment, log."""
        if new_sim_time.tzinfo is None:
            new_sim_time = new_sim_time.replace(tzinfo=UTC)
        for zid in list(self.state.zones):
            z = self.state.zones[zid]
            if z.state in ACTIVE_STATES:
                self._finish_cmd(zid, "failed", "Stopped due to virtual clock jump")
                z.state = "off"
                z.flow_m3h = 0.0
                z.pressure_bar = 0.0
                z.runtime_sec = 0
                v = self.state.valve_for_zone(zid)
                if v:
                    v.status = "closed"
                    v.last_command = "close"
                    self.phase_t.pop(f"valve:{v.valve_id}", None)
                self.phase_t.pop(zid, None)
                self.zone_abort.pop(zid, None)
                self.zone_cmd.pop(zid, None)
        for pump in self.state.pumps.values():
            pump.state = "stopped"
            pump.run_fb = False
        self.pump_t.clear()
        self.state.system.main_flow_m3h = 0.0
        self.state.system.main_pressure_bar = 0.0

        delta_s = (new_sim_time - self.sim_time).total_seconds()
        if delta_s > 0:
            hours = delta_s / 3600.0
            # Closed-form soil drying (avg ~0.6%/h)
            dry_pct = 0.6 * hours
            for z in self.state.zones.values():
                z.moisture_pct = min(95.0, max(10.0, z.moisture_pct - dry_pct))
            # Closed-form tank refill
            if self.state.system.refilling:
                refill_m3 = self.state.hyd.well_refill_flow_m3h * hours
                refill_pct = refill_m3 / self.state.hyd.tank_capacity_m3 * 100.0
                self.true_tank_pct = min(100.0, self.true_tank_pct + refill_pct)
                if self.true_tank_pct >= self.state.hyd.tank_refill_stop_pct:
                    self.state.system.refilling = False
                self.state.system.tank_level_pct = self.true_tank_pct

        self.sim_time = new_sim_time
        print(f"[SIMULATOR] Clock jumped to {new_sim_time.isoformat()} (skipped {delta_s:.0f}s)")

    def step(self, dt: float) -> None:
        """Advance the simulation by dt simulated seconds."""
        now = utcnow()
        if self.paused or self.timescale == 0 or dt <= 0:
            # Paused: zero physics steps, but keep sensor timestamps and objects fresh
            for sensor in self.state.sensors.values():
                sensor.timestamp = now
            for obj in (
                *self.state.zones.values(),
                *self.state.pumps.values(),
                *self.state.valves.values(),
            ):
                obj.last_updated = now
            return

        self.sim_time += timedelta(seconds=dt)
        self._step_protection()
        for zid in list(self.state.zones):
            self._step_zone(zid, dt)
        self._step_pumps(dt)
        self._step_valves(dt)
        self._step_hydraulics(dt)
        self._step_environment(dt)
        self._step_sensors()
        for obj in (
            *self.state.zones.values(),
            *self.state.pumps.values(),
            *self.state.valves.values(),
        ):
            obj.last_updated = now

    async def tick(self, dt: float) -> None:
        self.step(dt)

    async def run_loop(self) -> None:
        print(f"Simulator Engine started. Timescale: {self.timescale}x")
        self.running = True
        tick_interval = 1.0
        loop = asyncio.get_event_loop()
        while self.running:
            start = loop.time()
            if not self.paused and self.timescale > 0:
                sim_dt = tick_interval * self.timescale
                n = max(1, math.ceil(sim_dt / 2.0))
                for _ in range(n):
                    self.step(sim_dt / n)
            else:
                self.step(0.0)
            await asyncio.sleep(max(0, tick_interval - (loop.time() - start)))
