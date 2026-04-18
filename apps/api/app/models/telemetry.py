"""Telemetry models — time-series data and device state cache."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TelemetryPoint(Base):
    """Generic append-only telemetry table for all sensor/metric time-series data."""

    __tablename__ = "telemetry_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    farm_id: Mapped[str] = mapped_column(String(64), ForeignKey("farms.id"), nullable=False)
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.id"))
    device_type: Mapped[str | None] = mapped_column(String(20))
    device_id: Mapped[str | None] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(10), default="good")
    source: Mapped[str] = mapped_column(String(20), default="simulator")


class DeviceStateSnapshot(Base):
    """Denormalized current-state cache for quick lookups."""

    __tablename__ = "device_state_snapshots"

    device_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
