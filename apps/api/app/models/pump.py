"""Pump configuration and observed operating history."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Pump(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "pumps"

    farm_id: Mapped[str] = mapped_column(String(64), ForeignKey("farms.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100))
    pump_type: Mapped[str] = mapped_column(String(20), nullable=False)  # well | booster
    rated_flow_m3h: Mapped[float | None] = mapped_column(Float)
    rated_pressure_bar: Mapped[float | None] = mapped_column(Float)
    runtime_hours: Mapped[float] = mapped_column(Float, default=0.0)
    service_interval_hours: Mapped[int] = mapped_column(Integer, default=2000)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    farm = relationship("Farm", back_populates="pumps")


class PumpObservationSpan(Base):
    """A period of continuous feedback with the same observed running state."""

    __tablename__ = "pump_observation_spans"
    __table_args__ = (
        Index("ix_pump_observation_report", "pump_id", "source", "observed_from"),
        Index("ix_pump_observation_latest", "pump_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pump_id: Mapped[str] = mapped_column(String(64), ForeignKey("pumps.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    timeline: Mapped[str] = mapped_column(String(40), nullable=False)
    running: Mapped[bool | None] = mapped_column(Boolean)
    start_observed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sample_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
