"""Device Pydantic schemas — Pumps, Valves, Sensors."""

from datetime import datetime

from pydantic import BaseModel


# ── Pumps ────────────────────────────────────────────────

class PumpResponse(BaseModel):
    id: str
    farm_id: str
    code: str
    name: str
    name_ar: str | None = None
    pump_type: str
    rated_flow_m3h: float | None = None
    rated_pressure_bar: float | None = None
    runtime_hours: float
    service_interval_hours: int
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PumpUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    rated_flow_m3h: float | None = None
    rated_pressure_bar: float | None = None
    service_interval_hours: int | None = None
    enabled: bool | None = None


# ── Valves ───────────────────────────────────────────────

class ValveResponse(BaseModel):
    id: str
    zone_id: str
    code: str
    enabled: bool
    has_open_feedback: bool
    has_close_feedback: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ValveUpdate(BaseModel):
    enabled: bool | None = None


# ── Sensors ──────────────────────────────────────────────

class SensorResponse(BaseModel):
    id: str
    farm_id: str
    zone_id: str | None = None
    code: str
    sensor_type: str
    unit: str
    location_scope: str
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SensorUpdate(BaseModel):
    enabled: bool | None = None
    calibration_meta_json: str | None = None
