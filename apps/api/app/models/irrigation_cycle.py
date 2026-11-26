"""Irrigation cycle model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdentityMixin, TimestampMixin


class IrrigationCycle(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "irrigation_cycles"

    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(20), default="tank")
    program_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("programs.id", ondelete="SET NULL")
    )
    program_step_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("program_steps.id", ondelete="SET NULL")
    )
    command_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("commands.id", ondelete="SET NULL")
    )
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_duration_min: Mapped[int | None] = mapped_column(Integer)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(
        String(20)
    )  # completed | aborted | faulted | manual_stop | skipped
    initiated_by_type: Mapped[str] = mapped_column(String(20), default="user")
    initiated_by_id: Mapped[str | None] = mapped_column(String(64))
    water_estimate_m3: Mapped[float | None] = mapped_column(Float)
    water_is_estimate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    water_has_gaps: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    alarms_json: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
