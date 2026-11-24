"""Pydantic schemas for state mapping and syncing."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ZoneLiveState(BaseModel):
    zone_id: str
    state: str
    health: str
    source_mode: str | None = None
    pressure_bar: float | None = None
    flow_m3h: float | None = None
    moisture_pct: float | None = None
    runtime_sec: float = 0
    target_runtime_sec: float = 0
    active_alarm_count: int = 0
    panel_mode: str = "auto"
    run_source: str | None = None
    last_updated: datetime


class PumpLiveState(BaseModel):
    pump_id: str
    state: str
    run_fb: bool = False
    fault: bool = False
    runtime_hours: float = 0.0
    starts_today: int = 0
    panel_mode: str = "auto"
    power_kw: float = 0.0
    energy_kwh_today: float = 0.0
    current_a: float = 0.0
    last_updated: datetime


class ValveLiveState(BaseModel):
    valve_id: str
    status: str
    last_command: str
    last_updated: datetime


class SensorReading(BaseModel):
    sensor_id: str
    metric_key: str
    value: float
    unit: str
    quality: str
    timestamp: datetime


class FarmMapState(BaseModel):
    system_mode: str
    zones: list[ZoneLiveState]
    pumps: list[PumpLiveState]
    valves: list[ValveLiveState]
    sensors: list[SensorReading]
    tank_level_pct: float = 0.0
    main_pressure_bar: float = 0.0
    main_flow_m3h: float = 0.0
    active_alarms: list[Any] = []
    data_fresh: bool = True
    last_snapshot_ts: datetime | None = None
    farm_now: datetime | None = None
    speed: float = 1.0
    clock_mode: str = "real"
    clock_paused: bool = False
    power_ok: bool = True
    fallback_active: bool = False
    well_level_m: float | None = None
    filter_dp_bar: float | None = None

    model_config = ConfigDict(from_attributes=True)


class StateSyncPayload(BaseModel):
    """Payload sent by the simulator/plc to update device state cache."""

    device_key: str
    state_json: dict[str, Any]
    updated_at: datetime
