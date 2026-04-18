"""Alarm model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdentityMixin


class Alarm(Base, IdentityMixin):
    __tablename__ = "alarms"

    alarm_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(5), nullable=False)  # S0-S3
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active_unacked")
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.id"))
    device_type: Mapped[str | None] = mapped_column(String(20))
    device_id: Mapped[str | None] = mapped_column(String(64))
    source_layer: Mapped[str] = mapped_column(String(10), default="backend")  # plc | backend | derived
    current_value: Mapped[float | None] = mapped_column(Float)
    threshold_value: Mapped[float | None] = mapped_column(Float)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    message_ar: Mapped[str | None] = mapped_column(Text)
    message_en: Mapped[str | None] = mapped_column(Text)
    guidance_ar: Mapped[str | None] = mapped_column(Text)
    guidance_en: Mapped[str | None] = mapped_column(Text)
    correlation_key: Mapped[str | None] = mapped_column(String(64))
