"""Soil moisture start/stop levels per crop (G7). Values are % of available water."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CropMoistureLevel(Base):
    __tablename__ = "crop_moisture_levels"

    crop_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    start_pct: Mapped[float] = mapped_column(Float, nullable=False)
    stop_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(String(64))
