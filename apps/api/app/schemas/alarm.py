"""Alarm schemas (mirror the Alarm interface in contracts)."""

from datetime import datetime

from pydantic import BaseModel


class AlarmResponse(BaseModel):
    id: str
    alarm_code: str
    name: str
    name_ar: str | None = None
    severity: str
    category: str
    status: str
    zone_id: str | None = None
    device_type: str | None = None
    device_id: str | None = None
    source_layer: str
    current_value: float | None = None
    threshold_value: float | None = None
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    cleared_at: datetime | None = None
    reset_at: datetime | None = None
    reset_by: str | None = None
    message_en: str | None = None
    message_ar: str | None = None
    guidance_en: str | None = None
    guidance_ar: str | None = None
    condition_active: bool
    requires_ack: bool
    requires_manual_reset: bool
