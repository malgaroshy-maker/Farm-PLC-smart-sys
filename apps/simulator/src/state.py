"""Simulator memory state mapping."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SimZoneState(BaseModel):
    zone_id: str
    state: str = "off"
    health: str = "healthy"
    source_mode: str | None = None
    pressure_bar: float = 0.0
    flow_m3h: float = 0.0
    moisture_pct: float = 40.0
    runtime_sec: int = 0
    active_alarm_count: int = 0
    last_updated: datetime


class SimPumpState(BaseModel):
    pump_id: str
    state: str = "stopped"
    run_fb: bool = False
    fault: bool = False
    runtime_hours: float = 0.0
    last_updated: datetime


class SimValveState(BaseModel):
    valve_id: str
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
    """High-level system metrics."""
    system_mode: str = "auto"
    tank_level_pct: float = 90.0
    main_pressure_bar: float = 0.0
    main_flow_m3h: float = 0.0


class FarmSimulationState:
    """In-memory core state of the farm."""
    def __init__(self):
        self.system = SimSystemState()
        self.zones: dict[str, SimZoneState] = {}
        self.pumps: dict[str, SimPumpState] = {}
        self.valves: dict[str, SimValveState] = {}
        self.sensors: dict[str, SimSensorState] = {}

    def get_sync_payloads(self) -> list[dict]:
        """Convert to the list of payloads expected by /api/v1/state/sync"""
        payloads = []
        now = datetime.utcnow().isoformat()
        
        # System
        payloads.append({
            "device_key": "system_mode",
            "state_json": {"mode": self.system.system_mode},
            "updated_at": now
        })
        payloads.append({
            "device_key": "simulation_stats",
            "state_json": {
                "tank_level_pct": self.system.tank_level_pct,
                "main_pressure_bar": self.system.main_pressure_bar,
                "main_flow_m3h": self.system.main_flow_m3h
            },
            "updated_at": now
        })
        
        # Zones
        for z in self.zones.values():
            data = z.model_dump()
            data["last_updated"] = data["last_updated"].isoformat()
            payloads.append({
                "device_key": f"zone_{z.zone_id}",
                "state_json": data,
                "updated_at": now
            })
            
        # Pumps
        for p in self.pumps.values():
            data = p.model_dump()
            data["last_updated"] = data["last_updated"].isoformat()
            payloads.append({
                "device_key": f"pump_{p.pump_id}",
                "state_json": data,
                "updated_at": now
            })
            
        # Valves
        for v in self.valves.values():
            data = v.model_dump()
            data["last_updated"] = data["last_updated"].isoformat()
            payloads.append({
                "device_key": f"valve_{v.valve_id}",
                "state_json": data,
                "updated_at": now
            })
            
        # Sensors
        for s in self.sensors.values():
            data = s.model_dump()
            data["timestamp"] = data["timestamp"].isoformat()
            payloads.append({
                "device_key": f"sensor_{s.sensor_id}",
                "state_json": data,
                "updated_at": now
            })
            
        return payloads
