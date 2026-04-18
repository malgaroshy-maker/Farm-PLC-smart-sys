"""Farm Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class FarmResponse(BaseModel):
    """Farm detail response."""

    id: str
    name: str
    name_ar: str | None = None
    description: str | None = None
    timezone: str
    total_area_ha: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
