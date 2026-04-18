"""Pump model."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
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
