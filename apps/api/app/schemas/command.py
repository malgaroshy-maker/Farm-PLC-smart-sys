"""Pydantic schemas for Commands."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CommandCreate(BaseModel):
    command_type: str
    target_type: str
    target_id: str | None = None
    payload: dict[str, Any] | None = None


class CommandResponse(BaseModel):
    id: str
    command_type: str
    target_type: str
    target_id: str | None = None
    payload_json: str | None = None
    status: str
    requested_at: datetime
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CommandSyncUpdate(BaseModel):
    status: str
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
