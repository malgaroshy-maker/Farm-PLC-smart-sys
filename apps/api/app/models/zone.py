"""Zone and ZoneCombination models."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Zone(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "zones"

    farm_id: Mapped[str] = mapped_column(String(64), ForeignKey("farms.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100))
    crop_type: Mapped[str] = mapped_column(String(30), default="other")
    area_ha: Mapped[float | None] = mapped_column(Float)
    geometry_ref: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    source_preference: Mapped[str] = mapped_column(String(20), default="tank")
    allows_direct_well: Mapped[bool] = mapped_column(Boolean, default=False)
    max_runtime_min: Mapped[int] = mapped_column(Integer, default=120)
    default_duration_min: Mapped[int] = mapped_column(Integer, default=45)
    pressure_min_bar: Mapped[float] = mapped_column(Float, default=1.5)
    pressure_max_bar: Mapped[float] = mapped_column(Float, default=4.0)
    flow_min_m3h: Mapped[float] = mapped_column(Float, default=2.0)
    flow_max_m3h: Mapped[float] = mapped_column(Float, default=10.0)

    # Relationships
    farm = relationship("Farm", back_populates="zones")
    valves = relationship("Valve", back_populates="zone", lazy="selectin")
    schedules = relationship("Schedule", back_populates="zone", lazy="selectin")


class ZoneCombination(Base, TimestampMixin):
    __tablename__ = "zone_combinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_a_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    zone_b_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
