"""Schedule model."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Schedule(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "schedules"

    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    recurrence_rule: Mapped[str] = mapped_column(String(30), default="daily")
    start_time_local: Mapped[str] = mapped_column(String(10), nullable=False)  # HH:MM
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday_mask: Mapped[str | None] = mapped_column(String(20))  # "1,2,3,4,5"
    season: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    source_override: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    zone = relationship("Zone", back_populates="schedules")
