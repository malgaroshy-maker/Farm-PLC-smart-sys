"""Schemas for irrigation cycles."""

from datetime import datetime

from pydantic import BaseModel


class IrrigationCycleResponse(BaseModel):
    id: str
    zone_id: str
    source_mode: str
    program_id: str | None = None
    program_step_id: str | None = None
    command_id: str | None = None
    planned_start_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    planned_duration_min: int | None = None
    actual_duration_min: int | None = None
    outcome: str | None = None
    water_estimate_m3: float | None = None
    initiated_by_type: str = "user"
    initiated_by_id: str | None = None
    alarms_json: str | None = None
    failure_reason: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CyclesPageResponse(BaseModel):
    items: list[IrrigationCycleResponse]
    total: int
    page: int
    page_size: int
    pages: int
