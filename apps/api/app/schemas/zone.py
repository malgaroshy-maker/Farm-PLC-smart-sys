"""Zone Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


CROP_TYPES = ("pomegranate", "olives", "grapes", "mixed_fruit", "other")


class ZoneUpdate(BaseModel):
    """Zone partial update schema (Settings → Zones & equipment). Ranges are sanity limits."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    name_ar: str | None = Field(default=None, min_length=1, max_length=100)
    crop_type: Literal["pomegranate", "olives", "grapes", "mixed_fruit", "other"] | None = None
    area_ha: float | None = Field(default=None, gt=0, le=100)
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=99)
    source_preference: Literal["tank", "well"] | None = None
    allows_direct_well: bool | None = None
    max_runtime_min: int | None = Field(default=None, ge=1, le=720)
    default_duration_min: int | None = Field(default=None, ge=1, le=720)
    pressure_min_bar: float | None = Field(default=None, ge=0, le=10)
    pressure_max_bar: float | None = Field(default=None, ge=0, le=10)
    flow_min_m3h: float | None = Field(default=None, ge=0, le=100)
    flow_max_m3h: float | None = Field(default=None, ge=0, le=100)


class ZoneCreate(BaseModel):
    """New zone (+ its valve and moisture sensor). Shown on the map once its outline is traced."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,24}$")
    name: str = Field(min_length=1, max_length=100)
    name_ar: str = Field(min_length=1, max_length=100)
    crop_type: Literal["pomegranate", "olives", "grapes", "mixed_fruit", "other"] = "other"
    area_ha: float = Field(gt=0, le=100)
    max_runtime_min: int = Field(default=90, ge=1, le=720)
    default_duration_min: int = Field(default=45, ge=1, le=720)
    flow_min_m3h: float = Field(default=2.0, ge=0, le=100)
    flow_max_m3h: float = Field(default=8.0, ge=0, le=100)
    pressure_min_bar: float = Field(default=1.5, ge=0, le=10)
    pressure_max_bar: float = Field(default=4.0, ge=0, le=10)
