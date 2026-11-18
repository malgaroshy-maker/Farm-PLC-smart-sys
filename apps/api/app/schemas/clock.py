"""Pydantic schemas for simulation clock."""

from datetime import datetime

from pydantic import BaseModel, Field


class ClockResponse(BaseModel):
    mode: str
    speed: float
    paused: bool
    farm_now: datetime
    real_now: datetime


class ClockUpdateRequest(BaseModel):
    speed: float | None = Field(default=None, ge=0)
    pause: bool | None = None
    step_min: float | None = None
    jump_to: str | None = None
    real: bool | None = None
    confirm: bool | None = None
