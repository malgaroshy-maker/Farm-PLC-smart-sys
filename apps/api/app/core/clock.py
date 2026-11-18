"""
Virtual farm clock — the single source of truth for simulation time (SIMULATION_TIME.md).

State:
  * mode: "real" | "sim"
  * speed: float (0 = paused, 1 = normal, 10, 60, 360, …)
  * anchor_real: UTC datetime of the last state change
  * anchor_sim: UTC datetime the farm was at when anchor_real was recorded

farm_now() = anchor_sim + (real_now - anchor_real) * speed.
In real mode, or when CONTROLLER_MODE != "simulator", farm_now() = real_now.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.timeutil import as_utc, utcnow
from app.models.clock import FarmClockModel


class FarmClock:
    def __init__(self) -> None:
        now = utcnow()
        self.mode: str = "real"
        self.speed: float = 1.0
        self.anchor_real: datetime = now
        self.anchor_sim: datetime = now
        self.updated_at: datetime = now
        self._last_nonzero_speed: float = 1.0

    @property
    def is_paused(self) -> bool:
        return self.speed == 0.0

    @property
    def is_locked_real(self) -> bool:
        return settings.controller_mode != "simulator"

    def farm_now(self, real_now: datetime | None = None) -> datetime:
        """Current virtual time on the farm."""
        now = real_now or utcnow()
        if self.is_locked_real or self.mode == "real":
            return now
        delta = (now - self.anchor_real).total_seconds()
        return self.anchor_sim + timedelta(seconds=delta * self.speed)

    def _reanchor(self, real_now: datetime | None = None) -> None:
        """Capture the current sim time at real_now before any rate or anchor change."""
        now = real_now or utcnow()
        current_sim = self.farm_now(now)
        self.anchor_real = now
        self.anchor_sim = current_sim
        self.updated_at = now

    def set_speed(self, speed: float, real_now: datetime | None = None) -> None:
        if self.is_locked_real:
            raise ValueError("Clock is locked to real time in PLC controller mode")
        if speed < 0:
            raise ValueError("Clock speed cannot be negative")
        self._reanchor(real_now)
        if speed > 0:
            self._last_nonzero_speed = speed
        self.speed = float(speed)
        self.mode = "sim"

    def pause(self, real_now: datetime | None = None) -> None:
        if self.is_locked_real:
            raise ValueError("Clock is locked to real time in PLC controller mode")
        self._reanchor(real_now)
        if self.speed > 0:
            self._last_nonzero_speed = self.speed
        self.speed = 0.0
        self.mode = "sim"

    def resume(self, real_now: datetime | None = None) -> None:
        if self.is_locked_real:
            raise ValueError("Clock is locked to real time in PLC controller mode")
        self._reanchor(real_now)
        self.speed = self._last_nonzero_speed or 1.0
        self.mode = "sim"

    def step(self, step_min: float = 1.0, real_now: datetime | None = None) -> None:
        if self.is_locked_real:
            raise ValueError("Clock is locked to real time in PLC controller mode")
        self._reanchor(real_now)
        self.anchor_sim += timedelta(minutes=step_min)
        self.mode = "sim"

    def jump_to(self, time_str: str, real_now: datetime | None = None) -> tuple[datetime, datetime]:
        """Monotonic jump to the next occurrence of HH:MM in farm local time."""
        if self.is_locked_real:
            raise ValueError("Clock is locked to real time in PLC controller mode")
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}, expected HH:MM")
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError as err:
            raise ValueError(f"Invalid time numbers in {time_str}") from err
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Time out of range: {time_str}")

        self._reanchor(real_now)
        prev_sim = self.anchor_sim
        tz = ZoneInfo(settings.farm_timezone)
        local_sim = prev_sim.astimezone(tz)
        target_local = local_sim.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_local <= local_sim:
            target_local += timedelta(days=1)
        target_utc = target_local.astimezone(UTC)
        self.anchor_sim = target_utc
        self.mode = "sim"
        return prev_sim, target_utc

    def reset_to_real(self, real_now: datetime | None = None) -> None:
        now = real_now or utcnow()
        self.mode = "real"
        self.speed = 1.0
        self.anchor_real = now
        self.anchor_sim = now
        self.updated_at = now
        self._last_nonzero_speed = 1.0

    def as_dict(self, real_now: datetime | None = None) -> dict:
        now = real_now or utcnow()
        if self.is_locked_real:
            return {
                "mode": "real",
                "speed": 1.0,
                "paused": False,
                "farm_now": now,
                "real_now": now,
            }
        return {
            "mode": self.mode,
            "speed": self.speed,
            "paused": self.is_paused,
            "farm_now": self.farm_now(now),
            "real_now": now,
        }

    async def load(self, db: AsyncSession) -> None:
        result = await db.execute(select(FarmClockModel).where(FarmClockModel.id == 1))
        row = result.scalar_one_or_none()
        if row is None:
            now = utcnow()
            row = FarmClockModel(
                id=1,
                mode=self.mode,
                speed=self.speed,
                anchor_real=now,
                anchor_sim=now,
                updated_at=now,
            )
            db.add(row)
            await db.commit()
            return
        if self.is_locked_real:
            self.mode = "real"
            self.speed = 1.0
            return
        self.mode = row.mode
        self.speed = float(row.speed)
        if self.speed > 0:
            self._last_nonzero_speed = self.speed
        self.anchor_real = as_utc(row.anchor_real)
        self.anchor_sim = as_utc(row.anchor_sim)
        self.updated_at = as_utc(row.updated_at)

    async def save(self, db: AsyncSession) -> None:
        row = await db.get(FarmClockModel, 1)
        if row is None:
            row = FarmClockModel(id=1)
            db.add(row)
        row.mode = self.mode
        row.speed = self.speed
        row.anchor_real = self.anchor_real
        row.anchor_sim = self.anchor_sim
        row.updated_at = utcnow()
        await db.commit()


clock = FarmClock()
