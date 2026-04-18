"""Zone Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ZoneResponse(BaseModel):
    """Zone detail response."""

    id: str
    farm_id: str
    code: str
    name: str
    name_ar: str | None = None
    crop_type: str
    area_ha: float | None = None
    enabled: bool
    priority: int
    source_preference: str
    allows_direct_well: bool
    max_runtime_min: int
    default_duration_min: int
    pressure_min_bar: float
    pressure_max_bar: float
    flow_min_m3h: float
    flow_max_m3h: float
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ZoneUpdate(BaseModel):
    """Zone partial update schema."""

    name: str | None = None
    name_ar: str | None = None
    crop_type: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    source_preference: str | None = None
    allows_direct_well: bool | None = None
    max_runtime_min: int | None = None
    default_duration_min: int | None = None
    pressure_min_bar: float | None = None
    pressure_max_bar: float | None = None
    flow_min_m3h: float | None = None
    flow_max_m3h: float | None = None
