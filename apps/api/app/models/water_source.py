"""Water source model."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdentityMixin, TimestampMixin


class WaterSource(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "water_sources"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # tank | well_direct | hybrid
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    availability: Mapped[str] = mapped_column(String(20), default="available")
