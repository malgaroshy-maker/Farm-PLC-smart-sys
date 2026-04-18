"""Valve model."""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Valve(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "valves"

    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    has_open_feedback: Mapped[bool] = mapped_column(Boolean, default=True)
    has_close_feedback: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    zone = relationship("Zone", back_populates="valves")
