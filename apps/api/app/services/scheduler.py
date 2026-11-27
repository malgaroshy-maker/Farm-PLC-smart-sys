"""Virtual Farm Clock Scheduler service (Milestone D).

Drives scheduled programs strictly using clock.farm_now().
Never uses APScheduler or real wall-clock timers.
Monitors sequentially executing program steps and handles:
  - Pause (nothing fires)
  - Speed changes and clock jumps (missed runs rule: skip & log missed)
  - Interlocks and blocked starts (skip zone, log, raise S1 alarm, continue)
  - Monotonicity across restarts (persisted in scheduler_state table)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.core.domain import TERMINAL_COMMAND_STATUSES
from app.core.timeutil import as_utc, utcnow
from app.database import async_session_factory
from app.deps import Actor
from app.models.ai import ProgramOverride
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.program import Program, ProgramStep, SchedulerState
from app.models.zone import Zone
from app.schemas.command import CommandCreate
from app.services.commands import (
    CommandRejected,
    ProgramStopped,
    stopped_all_since,
    submit_command,
)
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
RESTART_GAP_SEC = 60.0  # a restart that took longer ends the program that was running
START_SHOWS_WITHIN_SEC = 20.0  # real time a controller has to show a zone it accepted


class SchedulerService:
    def __init__(self) -> None:
        self._last_farm_time: datetime | None = None
        self._last_real_time: datetime | None = None
        self._pending_jump: tuple[datetime, datetime] | None = None
        self._background: set = set()

    def on_clock_jump(
        self, new_farm_time: datetime, prev_farm_time: datetime | None = None
    ) -> None:
        """Register an explicit clock jump so scheduler immediately synchronizes."""
        prev = prev_farm_time or self._last_farm_time or new_farm_time
        self._pending_jump = (prev, new_farm_time)
        self._last_farm_time = new_farm_time

    def reset(self) -> None:
        self._last_farm_time = None
        self._last_real_time = None
        self._pending_jump = None

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
        now_real = utcnow()
        farm_tz = ZoneInfo(settings.farm_timezone)

        delta_real_sec = (
            (now_real - self._last_real_time).total_seconds()
            if self._last_real_time is not None
            else 0.0
        )
        self._last_real_time = now_real

        # Check for explicit clock jump first
        jump_range = self._pending_jump
        self._pending_jump = None
        if jump_range is not None:
            jump_from, jump_to = jump_range
            await self._cancel_active(db, "clock_jump")
            await self._handle_missed_runs(db, jump_from, jump_to, farm_tz)
            self._last_farm_time = now_farm
            await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
            await db.commit()
            return

        # 1. Initialize or load last_farm_time
        if self._last_farm_time is None:
            persisted = await self._get_state(db, STATE_LAST_FARM_TIME)
            if persisted:
                try:
                    restored = datetime.fromisoformat(persisted)
                except Exception:
                    restored = None
                if restored is not None and restored < now_farm:
                    # Fresh process (API restart): everything between the last
                    # recorded tick and now happened while we were down, so it
                    # follows the owner's "missed runs" rule — never catch up.
                    if (now_farm - restored).total_seconds() > RESTART_GAP_SEC:
                        await self._cancel_active(db, "app_was_down")
                    await self._handle_missed_runs(db, restored, now_farm, farm_tz)
                self._last_farm_time = now_farm
                await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
                await db.commit()
                return
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
            await self._cancel_active(db, "clock_jump")
            await db.commit()
            return
        if delta_sec == 0:
            return

        # 2. After a real gap (PC asleep, app frozen) nothing is caught up: the running program
        # ends before any of its steps can be looked at
        if delta_real_sec > 60.0:
            await self._cancel_active(db, "app_was_down")
            await self._handle_missed_runs(db, prev_farm, now_farm, farm_tz)
            self._last_farm_time = now_farm
            await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
            await db.commit()
            return

        # 3. Check active running program progress
        active_prog_json = await self._get_state(db, STATE_ACTIVE_PROGRAM)
        if active_prog_json:
            try:
                active_data = json.loads(active_prog_json)
                await self._process_active_program(db, active_data, snapshots)
            except Exception:
                log.exception("Error processing active scheduler program")

        from app.services.features import is_enabled

        # 4. Find programs due between prev_farm and now_farm (owner can pause automation)
        if await is_enabled(db, "automation.scheduler"):
            await self._check_due_programs(db, prev_farm, now_farm, farm_tz)

        # 5. Morning briefing (06:00) and evening weather advice (18:00) wait on the weather and
        # the AI for up to a minute. They run on their own, after this commit: inside the tick
        # they held SQLite's write lock, and STOP ALL failed with "database is locked".
        await db.commit()
        if self._crossed(prev_farm, now_farm, farm_tz, settings.ai_daily_briefing_time):
            if await is_enabled(db, "ai.briefing"):
                self._in_background(self._run_briefing(prev_farm, now_farm))
        if self._crossed(prev_farm, now_farm, farm_tz, "18:00"):
            if await is_enabled(db, "automation.advisor_auto") and await is_enabled(
                db, "ai.advisor"
            ):
                self._in_background(self._run_advisor(prev_farm, now_farm, farm_tz))

        # 6. Soil logic (G7): stop a full zone early, suggest an extra run for a dry one
        try:
            from app.services import soil

            if await soil.logic_on(db):
                await self._soil_logic(db, snapshots)
        except Exception:
            log.exception("Error running soil logic")

        self._last_farm_time = now_farm
        await self._set_state(db, STATE_LAST_FARM_TIME, now_farm.isoformat())
        await db.commit()

    @staticmethod
    def _crossed(prev_farm: datetime, now_farm: datetime, farm_tz: ZoneInfo, hhmm: str) -> bool:
        hour, minute = (int(x) for x in hhmm.split(":"))
        local = now_farm.astimezone(farm_tz)
        target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return prev_farm.astimezone(farm_tz) < target <= local

    def _in_background(self, work) -> None:
        task = asyncio.create_task(work)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _run_briefing(self, prev_farm: datetime, now_farm: datetime) -> None:
        from app.services.ai.briefing import check_scheduled_briefing

        try:
            async with async_session_factory() as db:
                await check_scheduled_briefing(db, prev_farm=prev_farm, now_farm=now_farm)
                await db.commit()
        except Exception:
            log.exception("Error checking scheduled morning briefing")

    async def _run_advisor(
        self, prev_farm: datetime, now_farm: datetime, farm_tz: ZoneInfo
    ) -> None:
        try:
            async with async_session_factory() as db:
                await self._maybe_auto_advise(db, prev_farm, now_farm, farm_tz)
                await db.commit()
        except Exception:
            log.exception("Error running the automatic weather advisor")

    async def _soil_logic(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> None:
        from app.models.ai import AISuggestion
        from app.services import soil

        status = await soil.soil_status(db, snapshots)
        stopped = getattr(self, "_soil_stopped", set())
        running = set()
        for zid, zs in status.items():
            live = snapshots.get(f"zone_{zid}")
            if not live or live.state.get("state") != "running":
                continue
            running.add(zid)
            # never fight a hand switch on the panel
            if live.state.get("panel_mode", "auto") != "auto" or zid in stopped:
                continue
            if zs.confirmed and zs.state == "full":
                try:
                    await submit_command(
                        db,
                        CommandCreate(
                            command_type="stop_zone",
                            target_type="zone",
                            target_id=zid,
                            payload={
                                "notes": f"Soil full: {zs.moisture:.0f}% (stop level {zs.stop:.0f}%)"
                            },
                        ),
                        SCHEDULER_ACTOR,
                    )
                    await log_event(
                        db,
                        "soil.stopped_early",
                        "zone",
                        zid,
                        actor_type="scheduler",
                        payload={"moisture_pct": zs.moisture, "stop_pct": zs.stop},
                    )
                    stopped.add(zid)
                except CommandRejected:
                    pass
        self._soil_stopped = stopped & running  # forget zones that have finished

        now = clock.farm_now()
        from app.services.ai.advisor import expire_suggestions

        await expire_suggestions(db)
        for zs in await soil.dry_without_run(db, status):
            pending = (
                (
                    await db.execute(
                        select(AISuggestion).where(
                            AISuggestion.feature == "soil",
                            AISuggestion.zone_id == zs.zone_id,
                            AISuggestion.status == "pending",
                        )
                    )
                )
                .scalars()
                .first()
            )
            if pending:
                continue
            zone = await db.get(Zone, zs.zone_id)
            name, name_ar = (
                (zone.name, zone.name_ar or zone.name) if zone else (zs.zone_id, zs.zone_id)
            )
            minutes = zone.default_duration_min if zone else 45
            db.add(
                AISuggestion(
                    id=f"sug_{uuid4().hex[:12]}",
                    feature="soil",
                    priority="medium",
                    status="pending",
                    title=f"Extra run for {name}",
                    title_ar=f"ري إضافي لمنطقة {name_ar}",
                    description=f"Soil at {zs.moisture:.0f}% of available water, below the start level of {zs.start:.0f}%, "
                    f"and no run is planned in the next 12 hours. Proposed: {minutes} min now.",
                    description_ar=f"رطوبة التربة {zs.moisture:.0f}% من الماء المتاح، أقل من مستوى البدء {zs.start:.0f}%، "
                    f"ولا يوجد ري مخطط خلال 12 ساعة. المقترح: {minutes} دقيقة الآن.",
                    reasoning="Server rule: confirmed start level, measured moisture, no upcoming run.",
                    reasoning_ar="قاعدة ثابتة: مستوى بدء مؤكد، رطوبة مقاسة، ولا ري قادم.",
                    action_payload_json=json.dumps(
                        {
                            "action": "extra_run",
                            "zone_id": zs.zone_id,
                            "duration_min": minutes,
                            "rule": "soil_dry_extra_run",
                            "inputs": [
                                {"key": "moisture_avg_pct", "value": zs.moisture, "unit": "%"},
                                {"key": "start_pct", "value": zs.start, "unit": "%"},
                            ],
                        }
                    ),
                    zone_id=zs.zone_id,
                    confidence=0.9,
                    created_at=now,
                    expires_at=now + timedelta(hours=12),
                )
            )
            await log_event(
                db,
                "soil.extra_run_suggested",
                "zone",
                zs.zone_id,
                actor_type="scheduler",
                payload={"moisture_pct": zs.moisture, "start_pct": zs.start},
            )

    async def _maybe_auto_advise(self, db, prev_farm, now_farm, farm_tz) -> None:
        """Once a day at 18:00 farm-local time, evaluate tomorrow's weather (Milestone G3)."""
        local_now = now_farm.astimezone(farm_tz)
        target = local_now.replace(hour=18, minute=0, second=0, microsecond=0)
        if not (prev_farm.astimezone(farm_tz) < target <= local_now):
            return
        from app.services.ai.advisor import evaluate_weather_advisor

        tomorrow = (local_now + timedelta(days=1)).strftime("%Y-%m-%d")
        log.info("Automatic weather advisor for %s", tomorrow)
        await evaluate_weather_advisor(db, target_date=tomorrow)

    async def _handle_missed_runs(
        self,
        db: AsyncSession,
        prev_farm: datetime,
        now_farm: datetime,
        farm_tz: ZoneInfo,
        reason: str = "clock jump or downtime",
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
                        "Program '%s' was missed (%s): %s -> %s",
                        prog.name,
                        reason,
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
                            "reason": reason,
                        },
                    )
                    await manager.broadcast(
                        "schedule.missed",
                        {
                            "program_id": prog.id,
                            "program_name": prog.name,
                            "scheduled_time": prog_dt.isoformat(),
                            "reason": reason,
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
            # a run that overruns (e.g. extended for heat) must not make the next one vanish
            await self._handle_missed_runs(
                db, prev_farm, now_farm, farm_tz, reason="another program was running"
            )
            return

        programs = await self._get_enabled_programs(db)
        prev_local = prev_farm.astimezone(farm_tz)
        now_local = now_farm.astimezone(farm_tz)

        curr_date = prev_local.date()
        end_date = now_local.date()

        while curr_date <= end_date:
            weekday = curr_date.isoweekday()
            date_str = curr_date.strftime("%Y-%m-%d")

            for prog in programs:
                if not self._is_weekday_active(prog.weekday_mask, weekday):
                    continue

                # Check if already fired on this date
                last_fired_key = f"scheduler.last_fired_{prog.id}"
                last_fired_date = await self._get_state(db, last_fired_key)
                if last_fired_date == date_str:
                    continue

                try:
                    h, m = map(int, prog.start_time_local.split(":"))
                    start_dt = datetime(
                        curr_date.year, curr_date.month, curr_date.day, h, m, tzinfo=farm_tz
                    )
                except Exception:
                    continue

                # Check if start time falls in (prev_local, now_local]
                if prev_local < start_dt <= now_local:
                    # Fire program!
                    await self._start_program(db, prog, date_str, last_fired_key)
                    return
            curr_date += timedelta(days=1)

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

        # Check for one-day AI program override
        override_stmt = (
            select(ProgramOverride)
            .where(
                ProgramOverride.target_date == today_date_str,
                ProgramOverride.applied.is_(False),
                (ProgramOverride.program_id == prog.id) | (ProgramOverride.program_id.is_(None)),
            )
            .order_by(desc(ProgramOverride.created_at))
            .limit(1)
        )
        res = await db.execute(override_stmt)
        override = res.scalar_one_or_none()

        duration_factor = 1.0
        if override:
            override.applied = True
            override.applied_at = clock.farm_now()
            await db.flush()

            if override.action == "skip":
                log.info(
                    "Program '%s' skipped on %s by approved AI override (%s)",
                    prog.name,
                    today_date_str,
                    override.id,
                )
                await log_event(
                    db,
                    "schedule.overridden",
                    "program",
                    prog.id,
                    actor_type="ai",
                    payload={
                        "override_id": override.id,
                        "action": "skip",
                        "target_date": today_date_str,
                        "reason": "AI Weather Advisor approved one-day override",
                    },
                )
                await manager.broadcast(
                    "schedule.overridden",
                    {
                        "program_id": prog.id,
                        "override_id": override.id,
                        "action": "skip",
                        "target_date": today_date_str,
                    },
                )
                return
            elif override.action in ("extend", "reduce"):
                duration_factor = float(override.duration_factor)
                log.info(
                    "Program '%s' duration adjusted by factor %.2f on %s by approved AI override (%s)",
                    prog.name,
                    duration_factor,
                    today_date_str,
                    override.id,
                )
                await log_event(
                    db,
                    "schedule.overridden",
                    "program",
                    prog.id,
                    actor_type="ai",
                    payload={
                        "override_id": override.id,
                        "action": override.action,
                        "duration_factor": duration_factor,
                        "target_date": today_date_str,
                    },
                )

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

        now_real = utcnow()
        active_data = {
            "started_real": now_real.isoformat(),
            "steps": self._signature(prog),
            "program_id": prog.id,
            "program_name": prog.name,
            "step_index": 0,
            "duration_factor": duration_factor,
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

        # G7 soil: a zone whose soil is already at its stop level is skipped (confirmed levels only)
        from app.services import soil
        from app.services.live_state import load_snapshots

        if await soil.logic_on(db):
            zs = (await soil.soil_status(db, await load_snapshots(db))).get(step.zone_id)
            if zs and zs.confirmed and zs.state == "full":
                reason = f"soil_full: soil at {zs.moisture:.0f}% (stop level {zs.stop:.0f}%)"
                await log_event(
                    db,
                    "schedule.skipped",
                    "zone",
                    step.zone_id,
                    actor_type="scheduler",
                    payload={"program_id": prog.id, "step_id": step.id, "reason": reason},
                )
                await manager.broadcast(
                    "schedule.skipped",
                    {
                        "program_id": prog.id,
                        "step_order": step.step_order,
                        "zone_id": step.zone_id,
                        "reason": reason,
                    },
                )
                await record_cycle_skipped(
                    db, prog.id, step.id, step.zone_id, step.duration_min, reason
                )
                await self._execute_program_step(db, prog, step_index + 1, active_data)
                return

        duration_factor = float(active_data.get("duration_factor", 1.0))
        effective_duration = max(1, int(round(step.duration_min * duration_factor)))
        note_suffix = f", override factor {duration_factor:.2f}" if duration_factor != 1.0 else ""

        cmd_req = CommandCreate(
            command_type="start_zone",
            target_type="zone",
            target_id=step.zone_id,
            payload={
                "duration_min": effective_duration,
                "program_id": prog.id,
                "program_step_id": step.id,
                "notes": f"Program: {prog.name} (Step {step.step_order}{note_suffix})",
            },
        )

        try:
            cmd = await submit_command(
                db, cmd_req, SCHEDULER_ACTOR, program_run_since=self._run_began(active_data)
            )
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
        except ProgramStopped:
            await self._cancel_program(db, prog.id, prog.name)
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
                "ALM-045",
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

        began = self._run_began(active_data)
        if began and await stopped_all_since(db, began):
            await self._cancel_program(db, prog_id, active_data.get("program_name"))
            return

        res = await db.execute(
            select(Program).options(selectinload(Program.steps)).where(Program.id == prog_id)
        )
        prog = res.scalar_one_or_none()
        why = await self._why_cancel(db, prog, active_data)
        if why:
            await self._cancel_program(db, prog_id, active_data.get("program_name"), why)
            return

        cmd = await db.get(Command, cmd_id)
        zone_snap = snapshots.get(f"zone_{zone_id}")
        zone_state = zone_snap.state.get("state") if zone_snap else "off"

        # Step is finished when command is terminal and zone is off/completed/faulted
        cmd_terminal = cmd is None or cmd.status in TERMINAL_COMMAND_STATUSES
        zone_idle = zone_state in ("off", "completed", "faulted")

        if not zone_idle:
            if not active_data.get("seen_running"):
                active_data["seen_running"] = True
                await self._set_state(db, STATE_ACTIVE_PROGRAM, json.dumps(active_data))
            return

        # A PLC completes the command as soon as it accepts it, before any snapshot shows the
        # zone: "off" then means "not yet", not "finished"
        if cmd and cmd.status == "completed" and not active_data.get("seen_running"):
            sent = as_utc(cmd.requested_at_real or cmd.requested_at)
            if (utcnow() - sent).total_seconds() < START_SHOWS_WITHIN_SEC:
                return

        if cmd_terminal:
            if await self._power_cut_ended_run(db, zone_id, cmd):
                # the owner decides what happens after a run that could not resume
                await self._cancel_program(db, prog.id, prog.name, "power_cut")
                return

            await manager.broadcast(
                "program.step_completed",
                {"program_id": prog.id, "step_index": step_index, "zone_id": zone_id},
            )
            await self._execute_program_step(db, prog, step_index + 1, active_data)

    @staticmethod
    def _run_began(active_data: dict) -> datetime | None:
        """Real time the run started (None for a run saved by an older version)."""
        value = active_data.get("started_real")
        return datetime.fromisoformat(value) if value else None

    @staticmethod
    def _signature(prog: Program) -> list:
        return [[s.step_order, s.zone_id, s.duration_min] for s in prog.steps]

    async def _why_cancel(
        self, db: AsyncSession, prog: Program | None, active_data: dict
    ) -> str | None:
        from app.services.features import is_enabled

        if prog is None:
            return "program_deleted"
        if not prog.enabled:
            return "program_switched_off"
        if not await is_enabled(db, "automation.scheduler"):
            return "automation_switched_off"
        saved = active_data.get("steps")
        if saved is not None and saved != self._signature(prog):
            return "program_edited"
        return None

    async def _power_cut_ended_run(self, db: AsyncSession, zone_id: str, cmd) -> bool:
        if cmd is None:
            return False
        found = await db.scalar(
            select(Alarm.id)
            .where(
                Alarm.alarm_code == "ALM-033",
                Alarm.zone_id == zone_id,
                Alarm.triggered_at >= cmd.requested_at,
            )
            .limit(1)
        )
        return found is not None

    async def _cancel_active(self, db: AsyncSession, reason: str) -> None:
        raw = await self._get_state(db, STATE_ACTIVE_PROGRAM)
        if not raw:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        await self._cancel_program(db, data.get("program_id"), data.get("program_name"), reason)

    async def _cancel_program(
        self, db: AsyncSession, prog_id: str | None, name: str | None, reason: str = "stop_all"
    ) -> None:
        await self._clear_state(db, STATE_ACTIVE_PROGRAM)
        await log_event(
            db,
            "program.cancelled",
            "program",
            prog_id,
            actor_type="scheduler",
            payload={"program_name": name, "reason": reason},
        )
        await manager.broadcast("program.finished", {"program_id": prog_id, "program_name": name})

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
