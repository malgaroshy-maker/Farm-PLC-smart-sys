"""Virtual Farm Clock Scheduler service (Milestone D).

Drives scheduled programs strictly using clock.farm_now().
Never uses APScheduler or real wall-clock timers.
Monitors sequentially executing program steps and handles:
  - Pause (nothing fires)
  - Speed changes and clock jumps (missed runs rule: skip & log missed)
  - Interlocks and blocked starts (skip zone, log, raise S1 alarm, continue)
  - Monotonicity across restarts (persisted in scheduler_state table)
"""

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.core.domain import TERMINAL_COMMAND_STATUSES
from app.deps import Actor
from app.models.command import Command
from app.models.program import Program, ProgramStep, SchedulerState
from app.schemas.command import CommandCreate
from app.services.commands import CommandRejected, submit_command
from app.services.cycles import record_cycle_skipped
from app.services.events import log_event
from app.services.live_state import Snapshot
from app.services.realtime import manager

log = logging.getLogger(__name__)

SCHEDULER_ACTOR = Actor(
    actor_type="scheduler",
    actor_id="scheduler",
    role="operator",
    name="Farm Scheduler",
)

STATE_LAST_FARM_TIME = "scheduler.last_farm_time"
STATE_ACTIVE_PROGRAM = "scheduler.active_program"
MISSED_RUN_GAP_SEC = 900.0  # 15 farm minutes gap indicates a clock jump or downtime


class SchedulerService:
    def __init__(self) -> None:
        self._last_farm_time: datetime | None = None

    def on_clock_jump(self, new_farm_time: datetime) -> None:
        """Reset tracked time on clock jump so scheduler immediately synchronizes."""
        self._last_farm_time = new_farm_time

    async def _get_state(self, db: AsyncSession, key: str) -> str | None:
        st = await db.get(SchedulerState, key)
        return st.value_text if st else None

    async def _set_state(self, db: AsyncSession, key: str, value: str | None) -> None:
        st = await db.get(SchedulerState, key)
        now = clock.farm_now()
        if not st:
            st = SchedulerState(key=key, value_text=value, updated_at=now)
            db.add(st)
        else:
            st.value_text = value
            st.updated_at = now
        await db.flush()

    async def _clear_state(self, db: AsyncSession, key: str) -> None:
        st = await db.get(SchedulerState, key)
        if st:
            await db.delete(st)
            await db.flush()

    async def tick(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> None:
        """Called on every monitor loop tick."""
        if clock.is_paused:
            return

        now_farm = clock.farm_now()
        farm_tz = ZoneInfo(settings.farm_timezone)

        # 1. Initialize or load last_farm_time
        if self._last_farm_time is None:
            persisted = await self._get_state(db, STATE_LAST_FARM_TIME)
            if persisted:
                try:
                    self._last_farm_time = datetime.fromisoformat(persisted)
                except Exception:
                    self._last_farm_time = now_farm
            else:
                self._last_farm_time = now_farm
                await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
                await db.commit()
                return

        prev_farm = self._last_farm_time
        delta_sec = (now_farm - prev_farm).total_seconds()
        if delta_sec < 0:
            # Clock jumped backward or resynced: immediately align to now_farm
            self._last_farm_time = now_farm
            await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
            await self._clear_state(db, STATE_ACTIVE_PROGRAM)
            await db.commit()
            return
        if delta_sec == 0:
            return

        # 2. Check active running program progress
        active_prog_json = await self._get_state(db, STATE_ACTIVE_PROGRAM)
        if active_prog_json:
            try:
                active_data = json.loads(active_prog_json)
                await self._process_active_program(db, active_data, snapshots)
            except Exception:
                log.exception("Error processing active scheduler program")

        # 3. Check for missed runs (Clock jump or outage)
        if delta_sec > MISSED_RUN_GAP_SEC:
            await self._handle_missed_runs(db, prev_farm, now_farm, farm_tz)
            self._last_farm_time = now_farm
            await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
            await db.commit()
            return

        # 4. Find programs due between prev_farm and now_farm
        await self._check_due_programs(db, prev_farm, now_farm, farm_tz)

        self._last_farm_time = now_farm
        await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
        await db.commit()

    async def _handle_missed_runs(
        self,
        db: AsyncSession,
        prev_farm: datetime,
        now_farm: datetime,
        farm_tz: ZoneInfo,
    ) -> None:
        """Apply owner decision on clock jumps: skip and log 'missed'."""
        programs = await self._get_enabled_programs(db)
        prev_local = prev_farm.astimezone(farm_tz)
        now_local = now_farm.astimezone(farm_tz)

        curr_date = prev_local.date()
        end_date = now_local.date()

        while curr_date <= end_date:
            weekday = curr_date.isoweekday()
            for prog in programs:
                if not self._is_weekday_active(prog.weekday_mask, weekday):
                    continue
                try:
                    h, m = map(int, prog.start_time_local.split(":"))
                    prog_dt = datetime(
                        curr_date.year, curr_date.month, curr_date.day, h, m, tzinfo=farm_tz
                    )
                except Exception:
                    continue

                if prev_local < prog_dt <= now_local:
                    log.warning(
                        "Program '%s' was missed due to clock jump (%s -> %s)",
                        prog.name,
                        prev_farm.isoformat(),
                        now_farm.isoformat(),
                    )
                    await log_event(
                        db,
                        "schedule.missed",
                        "program",
                        prog.id,
                        actor_type="scheduler",
                        payload={
                            "program_name": prog.name,
                            "scheduled_time": prog_dt.isoformat(),
                            "jump_from": prev_farm.isoformat(),
                            "jump_to": now_farm.isoformat(),
                        },
                    )
                    await manager.broadcast(
                        "schedule.missed",
                        {
                            "program_id": prog.id,
                            "program_name": prog.name,
                            "scheduled_time": prog_dt.isoformat(),
                            "reason": "clock jump or downtime",
                        },
                    )
            curr_date += timedelta(days=1)

    async def _check_due_programs(
        self,
        db: AsyncSession,
        prev_farm: datetime,
        now_farm: datetime,
        farm_tz: ZoneInfo,
    ) -> None:
        """Find programs whose start time arrived in the tick window."""
        # Only start a new program if no program is currently executing
        active_prog_json = await self._get_state(db, STATE_ACTIVE_PROGRAM)
        if active_prog_json:
            return

        programs = await self._get_enabled_programs(db)
        prev_local = prev_farm.astimezone(farm_tz)
        now_local = now_farm.astimezone(farm_tz)

        today_date_str = now_local.strftime("%Y-%m-%d")
        weekday = now_local.isoweekday()

        for prog in programs:
            if not self._is_weekday_active(prog.weekday_mask, weekday):
                continue

            # Check if already fired today
            last_fired_key = f"scheduler.last_fired_{prog.id}"
            last_fired_date = await self._get_state(db, last_fired_key)
            if last_fired_date == today_date_str:
                continue

            try:
                h, m = map(int, prog.start_time_local.split(":"))
                start_dt = datetime(
                    now_local.year, now_local.month, now_local.day, h, m, tzinfo=farm_tz
                )
            except Exception:
                continue

            # Check if start time falls in [prev_local, now_local]
            if prev_local < start_dt <= now_local:
                # Fire program!
                await self._start_program(db, prog, today_date_str, last_fired_key)
                break

    async def _start_program(
        self,
        db: AsyncSession,
        prog: Program,
        today_date_str: str,
        last_fired_key: str,
    ) -> None:
        if not prog.steps:
            return

        await self._set_state(db, last_fired_key, today_date_str)

        await log_event(
            db,
            "program.started",
            "program",
            prog.id,
            actor_type="scheduler",
            payload={"program_name": prog.name, "steps_count": len(prog.steps)},
        )
        await manager.broadcast(
            "program.started",
            {"program_id": prog.id, "program_name": prog.name, "steps_count": len(prog.steps)},
        )

        active_data = {
            "program_id": prog.id,
            "program_name": prog.name,
            "step_index": 0,
            "active_command_id": None,
            "active_zone_id": None,
        }
        await self._execute_program_step(db, prog, 0, active_data)

    async def _execute_program_step(
        self,
        db: AsyncSession,
        prog: Program,
        step_index: int,
        active_data: dict,
    ) -> None:
        if step_index >= len(prog.steps):
            # All steps done
            await self._finish_program(db, prog)
            return

        step: ProgramStep = prog.steps[step_index]
        active_data["step_index"] = step_index
        active_data["active_zone_id"] = step.zone_id

        cmd_req = CommandCreate(
            command_type="start_zone",
            target_type="zone",
            target_id=step.zone_id,
            payload={
                "duration_min": step.duration_min,
                "program_id": prog.id,
                "program_step_id": step.id,
                "notes": f"Program: {prog.name} (Step {step.step_order})",
            },
        )

        try:
            cmd = await submit_command(db, cmd_req, SCHEDULER_ACTOR)
            active_data["active_command_id"] = cmd.id
            await self._set_state(db, STATE_ACTIVE_PROGRAM, json.dumps(active_data))
            await log_event(
                db,
                "schedule.fired",
                "zone",
                step.zone_id,
                actor_type="scheduler",
                payload={
                    "program_id": prog.id,
                    "step_id": step.id,
                    "command_id": cmd.id,
                    "duration_min": step.duration_min,
                },
            )
            await manager.broadcast(
                "program.step_started",
                {
                    "program_id": prog.id,
                    "step_order": step.step_order,
                    "zone_id": step.zone_id,
                    "duration_min": step.duration_min,
                },
            )
        except CommandRejected as exc:
            # Blocked start rule: skip zone, log, raise S1 info alarm, continue program
            log.warning(
                "Scheduled step %d for zone %s blocked: %s",
                step.step_order,
                step.zone_id,
                exc.message,
            )
            await log_event(
                db,
                "schedule.skipped",
                "zone",
                step.zone_id,
                actor_type="scheduler",
                payload={
                    "program_id": prog.id,
                    "step_id": step.id,
                    "reason": f"{exc.code}: {exc.message}",
                },
            )
            await manager.broadcast(
                "schedule.skipped",
                {
                    "program_id": prog.id,
                    "step_order": step.step_order,
                    "zone_id": step.zone_id,
                    "reason": exc.message,
                },
            )
            await record_cycle_skipped(
                db,
                prog.id,
                step.id,
                step.zone_id,
                step.duration_min,
                f"{exc.code}: {exc.message}",
            )
            from app.services.alarms import engine as alarm_engine

            await alarm_engine.raise_event(
                db,
                "ALM-035",
                detail=f"Scheduled step skipped for zone {step.zone_id}: {exc.message}",
                zone_id=step.zone_id,
            )
            # Advance to next step
            await self._execute_program_step(db, prog, step_index + 1, active_data)

    async def _process_active_program(
        self,
        db: AsyncSession,
        active_data: dict,
        snapshots: dict[str, Snapshot],
    ) -> None:
        """Check if currently active step has finished."""
        prog_id = active_data.get("program_id")
        step_index = active_data.get("step_index", 0)
        cmd_id = active_data.get("active_command_id")
        zone_id = active_data.get("active_zone_id")

        if not cmd_id or not zone_id:
            await self._clear_state(db, STATE_ACTIVE_PROGRAM)
            return

        cmd = await db.get(Command, cmd_id)
        zone_snap = snapshots.get(f"zone_{zone_id}")
        zone_state = zone_snap.state.get("state") if zone_snap else "off"

        # Step is finished when command is terminal and zone is off/completed/faulted
        cmd_terminal = cmd is None or cmd.status in TERMINAL_COMMAND_STATUSES
        zone_idle = zone_state in ("off", "completed", "faulted")

        if cmd_terminal and zone_idle:
            # Advance to next step!
            res = await db.execute(
                select(Program).options(selectinload(Program.steps)).where(Program.id == prog_id)
            )
            prog = res.scalar_one_or_none()
            if not prog:
                await self._clear_state(db, STATE_ACTIVE_PROGRAM)
                return

            await manager.broadcast(
                "program.step_completed",
                {"program_id": prog.id, "step_index": step_index, "zone_id": zone_id},
            )
            await self._execute_program_step(db, prog, step_index + 1, active_data)

    async def _finish_program(self, db: AsyncSession, prog: Program) -> None:
        await self._clear_state(db, STATE_ACTIVE_PROGRAM)
        await log_event(
            db,
            "program.finished",
            "program",
            prog.id,
            actor_type="scheduler",
            payload={"program_name": prog.name},
        )
        await manager.broadcast(
            "program.finished",
            {"program_id": prog.id, "program_name": prog.name},
        )

    async def _get_enabled_programs(self, db: AsyncSession) -> list[Program]:
        res = await db.execute(
            select(Program)
            .options(selectinload(Program.steps))
            .where(Program.enabled.is_(True))
            .order_by(Program.start_time_local)
        )
        return list(res.scalars().all())

    def _is_weekday_active(self, weekday_mask: str, weekday: int) -> bool:
        days = {
            int(x.strip())
            for x in weekday_mask.split(",")
            if x.strip().isdigit() and 1 <= int(x.strip()) <= 7
        }
        return weekday in days


scheduler = SchedulerService()
