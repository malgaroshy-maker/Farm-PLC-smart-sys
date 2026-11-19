"""Program and ProgramStep models for sequential zone irrigation (Milestone D)."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdentityMixin, TimestampMixin


class Program(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "programs"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_time_local: Mapped[str] = mapped_column(String(10), nullable=False)  # HH:MM
    weekday_mask: Mapped[str] = mapped_column(
        String(30), default="1,2,3,4,5,6,7", nullable=False
    )  # "1,2,3,4,5,6,7" (1=Monday ... 7=Sunday)
    season: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))

    # Relationships
    steps: Mapped[list["ProgramStep"]] = relationship(
        "ProgramStep",
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramStep.step_order",
        lazy="selectin",
    )


class ProgramStep(Base, IdentityMixin, TimestampMixin):
    __tablename__ = "program_steps"

    program_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    program: Mapped["Program"] = relationship("Program", back_populates="steps")
    zone = relationship("Zone")


class SchedulerState(Base, TimestampMixin):
    __tablename__ = "scheduler_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_text: Mapped[str | None] = mapped_column(Text)
