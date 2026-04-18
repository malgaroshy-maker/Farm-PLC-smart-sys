"""Sensor model."""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Sensor(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "sensors"

    farm_id: Mapped[str] = mapped_column(String(64), ForeignKey("farms.id"), nullable=False)
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    location_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    calibration_meta_json: Mapped[str | None] = mapped_column(Text)

    # Relationships
    farm = relationship("Farm", back_populates="sensors")
