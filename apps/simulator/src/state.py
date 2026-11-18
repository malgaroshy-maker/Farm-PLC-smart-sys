"""Simulator memory state: configuration loaded from the API + live device state."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel


def utcnow() -> datetime:
    return datetime.now(UTC)


# ── Hydraulic constants ──────────────────────────────────
# Placeholders until the site survey gives real pump curves, pipe sizes and
# tank volume (PROJECT_STATUS → decisions). Kept in one place on purpose.


@dataclass
class Hydraulics:
    tank_capacity_m3: float = 150.0
    tank_refill_start_pct: float = 60.0
    tank_refill_stop_pct: float = 95.0
    well_refill_flow_m3h: float = 12.0
    # Booster on a VFD holding a pressure setpoint; it only falls below the
    # setpoint when demand exceeds the full-speed curve (shutoff - k·Q²).
    booster_setpoint_bar: float = 3.0
    booster_shutoff_bar: float = 5.0
    booster_k: float = 0.009  # bar per (m³/h)²
    well_setpoint_bar: float = 2.6  # direct-well zones run through a PRV
    well_shutoff_bar: float = 4.2
    well_k: float = 0.02
    nominal_pressure_bar: float = 2.5  # emitter design pressure
    leak_flow_at_nominal_m3h: float = 9.0
    pump_tau_s: float = 3.0  # pressure/flow first-order lag
    pump_start_s: float = 3.0
    pump_start_timeout_s: float = 8.0
    valve_travel_s: float = 4.0
    valve_timeout_s: float = 10.0
    flow_validation_s: float = 12.0
    leak_detect_s: float = 10.0
    tank_warning_pct: float = 25.0
    tank_critical_pct: float = 10.0
    tank_critical_clear_pct: float = 15.0


# ── Configuration (from API) ─────────────────────────────


@dataclass
class ZoneConfig:
    id: str
    code: str
    area_ha: float = 0.5
    allows_direct_well: bool = False
    default_duration_min: int = 45
    max_runtime_min: int = 120
    pressure_min_bar: float = 1.5
    pressure_max_bar: float = 4.0
    flow_min_m3h: float = 2.0
    flow_max_m3h: float = 10.0
    valve_id: str | None = None

    @property
    def nominal_flow_m3h(self) -> float:
        return (self.flow_min_m3h + self.flow_max_m3h) / 2


# ── Live state ───────────────────────────────────────────


class SimZoneState(BaseModel):
    zone_id: str
    state: str = "off"
    health: str = "healthy"
    source_mode: str | None = None
    pressure_bar: float = 0.0
    flow_m3h: float = 0.0
    moisture_pct: float = 40.0
    runtime_sec: float = 0
    target_runtime_sec: float = 0
    active_alarm_count: int = 0
    last_updated: datetime


class SimPumpState(BaseModel):
    pump_id: str
    pump_type: str = "booster"
    state: str = "stopped"
    run_fb: bool = False
    fault: bool = False
    runtime_hours: float = 0.0
    starts_today: int = 0
    last_updated: datetime


class SimValveState(BaseModel):
    valve_id: str
    zone_id: str = ""
    status: str = "closed"
    last_command: str = "none"
    last_updated: datetime


class SimSensorState(BaseModel):
    sensor_id: str
    metric_key: str
    value: float = 0.0
    unit: str = ""
    quality: str = "good"
    timestamp: datetime


class SimSystemState(BaseModel):
    system_mode: str = "auto"
    tank_level_pct: float = 80.0
    main_pressure_bar: float = 0.0
    main_flow_m3h: float = 0.0
    estop: bool = False
    refilling: bool = False


@dataclass
class AlarmCondition:
    """A protection condition the 'PLC' currently sees (reported to the backend)."""

    code: str
    zone_id: str | None = None
    device_id: str | None = None
    value: float | None = None
    threshold: float | None = None
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.code}:{self.zone_id or self.device_id or 'system'}"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "zone_id": self.zone_id,
            "device_id": self.device_id,
            "value": self.value,
            "threshold": self.threshold,
            "detail": self.detail,
        }


@dataclass
class Faults:
    """Injected world faults (what is physically broken)."""

    pump_trip: set[str] = field(default_factory=set)
    pump_fail_start: set[str] = field(default_factory=set)
    valve_stuck_closed: set[str] = field(default_factory=set)
    valve_stuck_open: set[str] = field(default_factory=set)
    zone_blocked: set[str] = field(default_factory=set)  # no flow despite open valve
    mainline_leak: bool = False
    tank_sensor_fault: bool = False
    comms_drop_until: datetime | None = None

    def clear_all(self) -> None:
        self.__init__()  # type: ignore[misc]


class FarmSimulationState:
    """In-memory core state of the farm."""

    def __init__(self):
        self.hyd = Hydraulics()
        self.system = SimSystemState()
        self.zone_cfg: dict[str, ZoneConfig] = {}
        self.zones: dict[str, SimZoneState] = {}
        self.pumps: dict[str, SimPumpState] = {}
        self.valves: dict[str, SimValveState] = {}
        self.sensors: dict[str, SimSensorState] = {}
        self.faults = Faults()
        self.alarms: dict[str, AlarmCondition] = {}

    # helpers
    def pump_of_type(self, pump_type: str) -> SimPumpState | None:
        return next((p for p in self.pumps.values() if p.pump_type == pump_type), None)

    def valve_for_zone(self, zone_id: str) -> SimValveState | None:
        cfg = self.zone_cfg.get(zone_id)
        return self.valves.get(cfg.valve_id) if cfg and cfg.valve_id else None

    def raise_alarm(self, cond: AlarmCondition) -> None:
        self.alarms[cond.key] = cond

    def clear_alarm(self, code: str, scope: str | None = None) -> None:
        self.alarms.pop(f"{code}:{scope or 'system'}", None)

    def get_sync_payloads(self) -> list[dict]:
        """Convert to the list of payloads expected by /api/v1/state/sync."""
        now = utcnow().isoformat()

        def item(key: str, data: dict) -> dict:
            return {"device_key": key, "state_json": data, "updated_at": now}

        payloads = [
            item("system_mode", {"mode": self.system.system_mode, "estop": self.system.estop}),
            item(
                "simulation_stats",
                {
                    "tank_level_pct": round(self.system.tank_level_pct, 2),
                    "main_pressure_bar": round(self.system.main_pressure_bar, 3),
                    "main_flow_m3h": round(self.system.main_flow_m3h, 3),
                    "refilling": self.system.refilling,
                },
            ),
            item("plc_alarms", {"active": [a.as_dict() for a in self.alarms.values()]}),
        ]
        for z in self.zones.values():
            payloads.append(item(f"zone_{z.zone_id}", z.model_dump(mode="json")))
        for p in self.pumps.values():
            payloads.append(item(f"pump_{p.pump_id}", p.model_dump(mode="json")))
        for v in self.valves.values():
            payloads.append(item(f"valve_{v.valve_id}", v.model_dump(mode="json")))
        for s in self.sensors.values():
            payloads.append(item(f"sensor_{s.sensor_id}", s.model_dump(mode="json")))
        return payloads
