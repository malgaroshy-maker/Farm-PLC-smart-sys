"""Pydantic schemas for Commands."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.domain import CommandStatus, CommandType


class CommandCreate(BaseModel):
    command_type: CommandType
    target_type: str = Field(max_length=20)
    target_id: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] | None = None


class CommandResponse(BaseModel):
    id: str
    command_type: str
    target_type: str
    target_id: str | None = None
    payload: dict[str, Any] | None = None
    requested_by: str | None = None
    actor_type: str
    status: str
    requested_at: datetime
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _decode_payload(cls, data: Any) -> Any:
        from app.core.timeutil import as_utc

        if isinstance(data, dict):
            for dt_field in ("requested_at", "acknowledged_at", "completed_at"):
                val = data.get(dt_field)
                if isinstance(val, datetime):
                    data[dt_field] = as_utc(val)
            return data

        raw = getattr(data, "payload_json", None)
        fields = {k: getattr(data, k, None) for k in cls.model_fields if k != "payload"}
        fields["payload"] = json.loads(raw) if raw else None

        for dt_field in ("requested_at", "acknowledged_at", "completed_at"):
            val = fields.get(dt_field)
            if isinstance(val, datetime):
                fields[dt_field] = as_utc(val)
        return fields


class CommandRejection(BaseModel):
    code: str
    message: str
    command_id: str


class CommandSyncUpdate(BaseModel):
    status: CommandStatus
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
