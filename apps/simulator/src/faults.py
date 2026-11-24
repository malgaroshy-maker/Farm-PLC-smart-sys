"""
Fault injection — breaks the simulated *world*; the PLC logic in engine.py reacts.

payload = {"target_type": ..., "target_id": ..., "fault_type": ..., "value": ...}

| target_type | fault_type                        | effect                                   |
|-------------|-----------------------------------|------------------------------------------|
| pump        | trip / fail_start / clear         | motor trip, no run feedback, repair       |
| valve       | stuck_closed / stuck_open / clear | actuator stuck, repair                    |
| valve       | hand_open / clear                 | someone opened the valve by hand (G7)     |
| zone        | blocked / clear                   | line/filter blocked → no flow             |
| system      | mainline_leak / clear_leak        | pipe burst on the mainline                |
| system      | estop / estop_release             | emergency stop button                     |
| system      | power_cut / power_restore         | mains power lost / back (G7)              |
| system      | well_low / well_recover           | aquifer drawn down / recovered (G7)       |
| system      | filter_clog / filter_clean        | head-unit filter fouled / flushed (G7)    |
| system      | clear_all                         | repair everything                         |
| sensor      | tank_level_fault / clear          | tank level reading frozen, quality bad    |
| tank        | set_level (value = %)             | teleport tank level (for scenarios)       |
| comms       | drop (value = seconds)            | simulator stops talking to the backend    |
"""

from datetime import timedelta
from typing import TYPE_CHECKING

from .state import utcnow

if TYPE_CHECKING:
    from .engine import SimulatorEngine


class FaultInjector:
    def __init__(self, engine: "SimulatorEngine"):
        self.engine = engine

    @property
    def state(self):
        return self.engine.state

    def handle(self, payload: dict) -> tuple[bool, str]:
        target_type = payload.get("target_type")
        target_id = payload.get("target_id")
        fault = payload.get("fault_type")
        handler = getattr(self, f"_{target_type}", None)
        if handler is None:
            return False, f"Unknown fault target '{target_type}'"
        return handler(target_id, fault, payload.get("value"))

    def _pump(self, pid, fault, _value):
        f = self.state.faults
        if pid not in self.state.pumps:
            return False, f"Pump {pid} not found"
        if fault == "trip":
            f.pump_trip.add(pid)
        elif fault == "fail_start":
            f.pump_fail_start.add(pid)
        elif fault == "clear":
            f.pump_trip.discard(pid)
            f.pump_fail_start.discard(pid)
        else:
            return False, f"Unknown pump fault '{fault}'"
        return True, "ok"

    def _valve(self, vid, fault, _value):
        f = self.state.faults
        if vid not in self.state.valves:
            return False, f"Valve {vid} not found"
        if fault == "stuck_closed":
            f.valve_stuck_closed.add(vid)
        elif fault == "stuck_open":
            f.valve_stuck_open.add(vid)
        elif fault == "hand_open":
            f.valve_hand_open.add(vid)
        elif fault == "clear":
            f.valve_stuck_closed.discard(vid)
            f.valve_stuck_open.discard(vid)
            f.valve_hand_open.discard(vid)
        else:
            return False, f"Unknown valve fault '{fault}'"
        return True, "ok"

    def _zone(self, zid, fault, _value):
        if zid not in self.state.zones:
            return False, f"Zone {zid} not found"
        if fault == "blocked":
            self.state.faults.zone_blocked.add(zid)
        elif fault == "clear":
            self.state.faults.zone_blocked.discard(zid)
        else:
            return False, f"Unknown zone fault '{fault}'"
        return True, "ok"

    def _system(self, _tid, fault, _value):
        s = self.state
        if fault == "mainline_leak":
            s.faults.mainline_leak = True
        elif fault == "clear_leak":
            s.faults.mainline_leak = False
        elif fault == "estop":
            s.system.estop = True
        elif fault == "estop_release":
            s.system.estop = False
        elif fault == "power_cut":
            s.faults.power_cut = True
        elif fault == "power_restore":
            s.faults.power_cut = False
        elif fault == "well_low":
            s.faults.well_low = True
        elif fault == "well_recover":
            s.faults.well_low = False
            s.system.well_level_m = s.hyd.well_static_m
        elif fault == "filter_clog":
            s.system.filter_dp_bar = 0.7
        elif fault == "filter_clean":
            s.system.filter_dp_bar = s.hyd.filter_clean_dp_bar
        elif fault == "clear_all":
            s.faults.clear_all()
            s.system.estop = False
        else:
            return False, f"Unknown system fault '{fault}'"
        return True, "ok"

    def _sensor(self, sid, fault, _value):
        if fault == "tank_level_fault":
            self.state.faults.tank_sensor_fault = True
        elif fault == "clear":
            self.state.faults.tank_sensor_fault = False
        else:
            return False, f"Unknown sensor fault '{fault}'"
        return True, "ok"

    def _tank(self, _tid, fault, value):
        if fault != "set_level" or value is None:
            return False, "tank needs fault_type 'set_level' and a value"
        level = max(0.0, min(100.0, float(value)))
        self.engine.true_tank_pct = level
        if not self.state.faults.tank_sensor_fault:
            self.state.system.tank_level_pct = level
        return True, "ok"

    def _comms(self, _tid, fault, value):
        if fault != "drop":
            return False, "comms needs fault_type 'drop'"
        seconds = max(1.0, min(600.0, float(value or 45)))
        self.state.faults.comms_drop_until = utcnow() + timedelta(seconds=seconds)
        return True, "ok"
