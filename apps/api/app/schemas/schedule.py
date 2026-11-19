"""Schemas for programs, steps and upcoming schedule runs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProgramStepSchema(BaseModel):
    id: str
    program_id: str
    zone_id: str
    step_order: int
    duration_min: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProgramStepCreate(BaseModel):
    zone_id: str
    step_order: int = Field(ge=1)
    duration_min: int = Field(ge=1)


class ProgramResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    start_time_local: str
    weekday_mask: str
    season: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[ProgramStepSchema] = []
    total_duration_min: int = 0

    model_config = {"from_attributes": True}


class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    start_time_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    weekday_mask: str = "1,2,3,4,5,6,7"
    season: str | None = None
    notes: str | None = None
    steps: list[ProgramStepCreate] = Field(min_length=1)


class ProgramUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    start_time_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    weekday_mask: str | None = None
    season: str | None = None
    notes: str | None = None
    steps: list[ProgramStepCreate] | None = None


class ProgramToggle(BaseModel):
    enabled: bool


class UpcomingRun(BaseModel):
    program_id: str
    program_name: str
    step_order: int
    zone_id: str
    zone_name: str
    zone_name_ar: str | None = None
    crop_type: str | None = None
    scheduled_start_farm: str
    duration_min: int
    seconds_until_start: float


class ConflictDetail(BaseModel):
    code: str
    message_en: str
    message_ar: str
    details: dict[str, Any] = {}
