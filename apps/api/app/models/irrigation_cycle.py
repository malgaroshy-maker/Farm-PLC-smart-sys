"""Irrigation cycle model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdentityMixin, TimestampMixin


class IrrigationCycle(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "irrigation_cycles"

    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(20), default="tank")
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_duration_min: Mapped[int | None] = mapped_column(Integer)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(String(20))  # completed | aborted | faulted | manual_stop
    initiated_by_type: Mapped[str] = mapped_column(String(20), default="user")
    initiated_by_id: Mapped[str | None] = mapped_column(String(64))
    water_estimate_m3: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
