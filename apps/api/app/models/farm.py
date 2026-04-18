"""Farm model."""

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Farm(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "farms"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Tripoli")
    total_area_ha: Mapped[float | None] = mapped_column(Float)

    # Relationships
    zones = relationship("Zone", back_populates="farm", lazy="selectin")
    pumps = relationship("Pump", back_populates="farm", lazy="selectin")
    sensors = relationship("Sensor", back_populates="farm", lazy="selectin")
