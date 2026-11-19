"""
Scenario runner (SIMULATION_PLAN.md §5) — scripted demos and acceptance checks.

Scenarios issue commands through the normal command service as a system actor,
so interlocks and the audit trail apply exactly as for an operator. World
faults go through `inject_fault`. One scenario runs at a time.

Steps
  ("fault", target_type, target_id, fault_type[, value])
  ("cmd", command_type, target_type, target_id[, payload])
  ("wait", seconds)
  ("wait_zone", zone_id, {states}, timeout_s)
  ("wait_alarm", alarm_code, timeout_s)
  ("note", message)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.database import async_session_factory
from app.deps import Actor
from app.models.alarm import Alarm
from app.schemas.command import CommandCreate
from app.services import commands as cmd_svc
from app.services.alarms import engine as alarm_engine
from app.services.live_state import load_snapshots
from app.services.realtime import manager

log = logging.getLogger(__name__)

SCENARIO_ACTOR = Actor(actor_type="system", actor_id=None, role="owner_admin", name="scenario")
RUNNING = {"running"}
DONE = {"completed", "faulted", "off"}

PREP = [
    ("note", "Preparing: repairing faults, stopping zones, filling tank"),
    ("fault", "system", None, "clear_all"),
    ("cmd", "stop_all", "system", None),
    ("cmd", "set_mode", "system", None, {"mode": "auto"}),
    ("fault", "tank", None, "set_level", 80),
    ("wait", 6),
    ("reset_alarms",),
]


@dataclass
class Scenario:
    name: str
    title: str
    title_ar: str
    description: str
    expect: list[str]
    steps: list[tuple]
    prep: bool = True


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in [
        Scenario(
            "normal_cycle",
            "Normal tank-fed cycle",
            "دورة ري عادية من الخزان",
            "Start Pomegranate 1 for 2 minutes and let it finish on its own.",
            [],
            [
                ("cmd", "start_zone", "zone", "zone_rumman_1", {"duration_min": 2}),
                ("wait_zone", "zone_rumman_1", RUNNING, 60),
                ("note", "Zone running — watch pressure, flow and tank level"),
                ("wait_zone", "zone_rumman_1", DONE, 400),
            ],
        ),
        Scenario(
            "direct_well_cycle",
            "Direct-well cycle on low tank",
            "ري مباشر من البئر عند انخفاض الخزان",
            "Tank at 20 % → Grapes (direct-well allowed) runs from the well pump.",
            ["ALM-001"],
            [
                ("fault", "tank", None, "set_level", 20),
                ("wait", 7),
                ("cmd", "start_zone", "zone", "zone_enab", {"duration_min": 2}),
                ("wait_zone", "zone_enab", RUNNING, 60),
                ("wait_alarm", "ALM-001", 30),
            ],
        ),
        Scenario(
            "tank_critical_during_run",
            "Tank critical during a run",
            "الخزان حرج أثناء الري",
            "Olives running, then the tank drops below 10 % → PLC stops the zone.",
            ["ALM-002"],
            [
                ("cmd", "start_zone", "zone", "zone_zaytoun", {"duration_min": 30}),
                ("wait_zone", "zone_zaytoun", RUNNING, 60),
                ("fault", "tank", None, "set_level", 9),
                ("wait_alarm", "ALM-002", 30),
                ("wait_zone", "zone_zaytoun", DONE, 30),
            ],
        ),
        Scenario(
            "booster_failed_start",
            "Booster pump fails to start",
            "فشل تشغيل مضخة التعزيز",
            "Booster gives no run feedback → start aborted.",
            ["ALM-006"],
            [
                ("fault", "pump", "pump_booster_01", "fail_start"),
                ("wait", 3),
                ("cmd", "start_zone", "zone", "zone_rumman_2"),
                ("wait_alarm", "ALM-006", 40),
                ("note", "Repairing the booster — reset ALM-006 in the Alarm Center"),
                ("fault", "pump", "pump_booster_01", "clear"),
            ],
        ),
        Scenario(
            "pump_trip_mid_cycle",
            "Booster trips mid-cycle",
            "فصل مضخة التعزيز أثناء الري",
            "Booster trips while Pomegranate 1 runs → zone stops, critical alarm latches.",
            ["ALM-005"],
            [
                ("cmd", "start_zone", "zone", "zone_rumman_1", {"duration_min": 10}),
                ("wait_zone", "zone_rumman_1", RUNNING, 60),
                ("wait", 8),
                ("fault", "pump", "pump_booster_01", "trip"),
                ("wait_alarm", "ALM-005", 30),
                ("wait", 10),
                ("note", "Repairing the pump — the alarm stays latched until an admin resets it"),
                ("fault", "pump", "pump_booster_01", "clear"),
            ],
        ),
        Scenario(
            "valve_failed_open",
            "Valve fails to open",
            "فشل فتح الصمام",
            "Pomegranate 3 valve is stuck closed → start aborted.",
            ["ALM-019"],
            [
                ("fault", "valve", "valve_rumman_3", "stuck_closed"),
                ("wait", 3),
                ("cmd", "start_zone", "zone", "zone_rumman_3"),
                ("wait_alarm", "ALM-019", 60),
                ("fault", "valve", "valve_rumman_3", "clear"),
            ],
        ),
        Scenario(
            "no_flow",
            "No flow after valve opens",
            "عدم وجود تدفق بعد فتح الصمام",
            "Blocked lateral on Pomegranate 4 → flow validation fails.",
            ["ALM-012"],
            [
                ("fault", "zone", "zone_rumman_4", "blocked"),
                ("wait", 3),
                ("cmd", "start_zone", "zone", "zone_rumman_4"),
                ("wait_alarm", "ALM-012", 60),
                ("fault", "zone", "zone_rumman_4", "clear"),
            ],
        ),
        Scenario(
            "valve_failed_close",
            "Valve fails to close",
            "فشل إغلاق الصمام",
            "Pomegranate 5 valve sticks open on stop → PLC isolates by stopping the pump.",
            ["ALM-020"],
            [
                ("cmd", "start_zone", "zone", "zone_rumman_5", {"duration_min": 10}),
                ("wait_zone", "zone_rumman_5", RUNNING, 60),
                ("fault", "valve", "valve_rumman_5", "stuck_open"),
                ("cmd", "stop_zone", "zone", "zone_rumman_5"),
                ("wait_alarm", "ALM-020", 60),
                ("wait", 8),
                ("note", "Valve closed by hand — reset ALM-020 after confirming"),
                ("fault", "valve", "valve_rumman_5", "clear"),
            ],
        ),
        Scenario(
            "mainline_leak",
            "Mainline leak",
            "تسريب في الخط الرئيسي",
            "Pipe bursts while Olives run → high flow detected, zone stopped.",
            ["ALM-013"],
            [
                ("cmd", "start_zone", "zone", "zone_zaytoun", {"duration_min": 20}),
                ("wait_zone", "zone_zaytoun", RUNNING, 60),
                ("wait", 6),
                ("fault", "system", None, "mainline_leak"),
                ("wait_alarm", "ALM-013", 60),
                ("wait", 6),
                ("fault", "system", None, "clear_leak"),
            ],
        ),
        Scenario(
            "emergency_stop",
            "Emergency stop",
            "إيقاف الطوارئ",
            "E-stop pressed during a run → everything stops; release, then reset.",
            ["ALM-041"],
            [
                ("cmd", "start_zone", "zone", "zone_rumman_6", {"duration_min": 10}),
                ("wait_zone", "zone_rumman_6", RUNNING, 60),
                ("fault", "system", None, "estop"),
                ("wait_alarm", "ALM-041", 30),
                ("wait", 10),
                ("fault", "system", None, "estop_release"),
            ],
        ),
        Scenario(
            "comms_loss",
            "Communication loss",
            "فقدان الاتصال",
            "Simulator goes silent for 45 s → stale data, then comms-lost alarm.",
            ["ALM-044", "ALM-029"],
            [
                ("fault", "comms", None, "drop", 45),
                ("wait_alarm", "ALM-044", 20),
                ("wait_alarm", "ALM-029", 45),
                ("note", "Waiting for comms to come back"),
                ("wait", 20),
            ],
        ),
        Scenario(
            "repeated_fault",
            "Repeated fault on one zone",
            "عطل متكرر في منطقة واحدة",
            "Three failed starts on New Pomegranate → maintenance advisory.",
            ["ALM-019", "ALM-036"],
            [
                ("fault", "valve", "valve_rumman_jadeed", "stuck_closed"),
                ("wait", 3),
                *[
                    step
                    for _ in range(3)
                    for step in (
                        ("cmd", "start_zone", "zone", "zone_rumman_jadeed"),
                        ("wait_zone", "zone_rumman_jadeed", {"faulted"}, 60),
                        ("wait", 4),
                    )
                ],
                ("wait_alarm", "ALM-036", 30),
                ("fault", "valve", "valve_rumman_jadeed", "clear"),
            ],
        ),
        Scenario(
            "scheduled_day",
            "Scheduled irrigation day",
            "يوم ري مجدول",
            "Create a 3-zone program, jump to 5 min before start, run at 60×, and verify three completed cycles.",
            [],
            [
                (
                    "create_program",
                    "Scheduled Day Demo",
                    "06:00",
                    "1,2,3,4,5,6,7",
                    [
                        ("zone_rumman_1", 2),
                        ("zone_rumman_2", 2),
                        ("zone_enab", 2),
                    ],
                ),
                ("clock_speed", 1.0),
                ("clock_jump", "05:55"),
                ("note", "Jumped to 05:55 on farm clock. Setting speed to 60×..."),
                ("clock_speed", 60.0),
                ("wait_completed_cycles", 3, 180),
                ("clock_speed", 1.0),
                ("note", "Program completed all 3 zones with water > 0. Returned to 1×."),
            ],
        ),
        Scenario(
            "scheduled_blocked_start",
            "Blocked scheduled start",
            "تعذر بدء مرحلة مجدولة",
            "Scheduled program on low tank skips blocked zone, raises S1 info alarm, and continues.",
            ["ALM-045"],
            [
                (
                    "create_program",
                    "Low Tank Sequence",
                    "07:00",
                    "1,2,3,4,5,6,7",
                    [
                        ("zone_rumman_1", 2),
                        ("zone_enab", 2),
                    ],
                ),
                ("fault", "tank", None, "set_level", 8),
                ("clock_speed", 1.0),
                ("clock_jump", "06:55"),
                ("clock_speed", 60.0),
                ("wait_skipped_cycle", "zone_rumman_1", 60),
                ("wait_completed_cycles", 1, 120),
                ("fault", "tank", None, "set_level", 80),
                ("clock_speed", 1.0),
            ],
        ),
        Scenario(
            "reset_farm",
            "Reset farm",
            "إعادة ضبط المزرعة",
            "Repair all faults, stop all zones, refill tank, reset latched alarms.",
            [],
            [],
        ),
    ]
}


@dataclass
class RunState:
    name: str | None = None
    status: str = "idle"  # idle | running | passed | failed | stopped
    step: int = 0
    total: int = 0
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    log: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class ScenarioFailed(Exception):
    pass


async def cleanup_scenario_programs(db: AsyncSession) -> int:
    """Delete all scenario-created programs (id starting with prog_scen_) and their steps/state."""
    from sqlalchemy import delete, select

    from app.models.program import Program, SchedulerState

    res = await db.execute(select(Program).where(Program.id.like("prog_scen_%")))
    progs = res.scalars().all()
    count = len(progs)
    for p in progs:
        await db.execute(delete(SchedulerState).where(SchedulerState.key.like(f"%{p.id}%")))
        await db.delete(p)
    if count > 0:
        await db.commit()
    return count


class ScenarioRunner:
    def __init__(self) -> None:
        self.state = RunState()
        self._task: asyncio.Task | None = None
        self._started = utcnow()
        self._started_farm = clock.farm_now()
        self._picked_up_at = utcnow()  # when the controller took the last command
        self.poll_s = 0.5
        self.pickup_timeout_s = 10.0

    def catalog(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "title": s.title,
                "title_ar": s.title_ar,
                "description": s.description,
                "expect": s.expect,
                "steps": len(s.steps) + (len(PREP) if s.prep else 0),
            }
            for s in SCENARIOS.values()
        ]

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, name: str) -> RunState:
        scenario = SCENARIOS.get(name)
        if not scenario:
            raise HTTPException(404, f"Unknown scenario '{name}'")
        if self.busy:
            raise HTTPException(409, f"Scenario '{self.state.name}' is still running")
        steps = (PREP if scenario.prep else []) + scenario.steps
        self._started = utcnow()
        self._started_farm = clock.farm_now()
        self.state = RunState(
            name=name, status="running", total=len(steps), started_at=utcnow().isoformat()
        )
        self._task = asyncio.create_task(self._run(scenario, steps))
        return self.state

    async def stop(self) -> RunState:
        if self.busy and self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        return self.state

    async def _publish(self, message: str | None = None) -> None:
        if message:
            self.state.message = message
            self.state.log.append(f"{utcnow().strftime('%H:%M:%S')} {message}")
        await manager.broadcast("scenario.updated", self.state.as_dict())

    async def _run(self, scenario: Scenario, steps: list[tuple]) -> None:
        await self._publish(f"Started: {scenario.title}")
        try:
            for i, step in enumerate(steps, 1):
                self.state.step = i
                await self._step(step)
            for code in scenario.expect:
                await self._wait_alarm(code, 1)
            self.state.status = "passed"
            await self._publish(
                "Finished — all expected alarms seen" if scenario.expect else "Finished"
            )
        except asyncio.CancelledError:
            self.state.status = "stopped"
            await self._publish("Stopped by user")
            raise
        except (ScenarioFailed, HTTPException, cmd_svc.CommandRejected) as exc:
            self.state.status = "failed"
            detail = getattr(exc, "message", None) or getattr(exc, "detail", None) or str(exc)
            await self._publish(f"Failed at step {self.state.step}: {detail}")
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("scenario crashed")
            self.state.status = "failed"
            await self._publish(f"Crashed: {exc}")
        finally:
            try:
                async with async_session_factory() as db:
                    await cleanup_scenario_programs(db)
            except Exception:
                log.exception("Failed to clean up scenario programs")
            self.state.finished_at = utcnow().isoformat()
            await self._publish()

    async def _step(self, step: tuple) -> None:
        kind = step[0]
        if kind == "note":
            await self._publish(step[1])
        elif kind == "wait":
            await asyncio.sleep(step[1])
        elif kind == "fault":
            _, target_type, target_id, fault_type, *rest = step
            payload = {"target_type": target_type, "target_id": target_id, "fault_type": fault_type}
            if rest:
                payload["value"] = rest[0]
            await self._command("inject_fault", "simulator", None, payload)
            await self._publish(
                f"Fault: {target_type} {target_id or ''} {fault_type}".replace("  ", " ")
            )
        elif kind == "cmd":
            _, ctype, target_type, target_id, *rest = step
            await self._command(ctype, target_type, target_id, rest[0] if rest else None)
            await self._publish(f"Command: {ctype} {target_id or ''}".strip())
        elif kind == "wait_zone":
            _, zone_id, states, timeout = step
            await self._wait_zone(zone_id, states, timeout)
        elif kind == "wait_alarm":
            await self._wait_alarm(step[1], step[2])
            await self._publish(f"Alarm raised: {step[1]}")
        elif kind == "reset_alarms":
            async with async_session_factory() as db:
                n = await alarm_engine.reset_all_cleared(db, SCENARIO_ACTOR)
            if n:
                await self._publish(f"Reset {n} latched alarm(s)")
        elif kind == "create_program":
            _, prog_name, start_time, weekday_mask, steps_list = step
            from uuid import uuid4

            from app.models.program import Program, ProgramStep

            async with async_session_factory() as db:
                p_id = f"prog_scen_{uuid4().hex[:8]}"
                now = clock.farm_now()
                prog = Program(
                    id=p_id,
                    name=prog_name,
                    enabled=True,
                    start_time_local=start_time,
                    weekday_mask=weekday_mask,
                    created_at=now,
                    updated_at=now,
                )
                db.add(prog)
                for idx, (zid, dur) in enumerate(steps_list, start=1):
                    st_id = f"step_scen_{uuid4().hex[:8]}"
                    db.add(
                        ProgramStep(
                            id=st_id,
                            program_id=p_id,
                            zone_id=zid,
                            step_order=idx,
                            duration_min=dur,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                await db.commit()
            await self._publish(f"Created program '{prog_name}' with {len(steps_list)} steps")
        elif kind == "clock_speed":
            speed = float(step[1])
            clock.set_speed(speed)
            async with async_session_factory() as db:
                await clock.save(db)
            await manager.broadcast(
                "clock.changed",
                {"speed": speed, "farm_now": clock.farm_now().isoformat()},
            )
            await self._publish(f"Clock speed set to {speed}×")
        elif kind == "clock_jump":
            time_str = step[1]
            prev_sim, next_sim = clock.jump_to(time_str)
            self._started_farm = next_sim
            async with async_session_factory() as db:
                from app.schemas.command import CommandCreate
                from app.services.commands import _supersede_starts
                from app.services.cycles import record_cycles_aborted_on_jump
                from app.services.scheduler import scheduler

                await _supersede_starts(
                    db, CommandCreate(command_type="stop_all", target_type="system")
                )
                await record_cycles_aborted_on_jump(db, next_sim)
                scheduler.on_clock_jump(next_sim, prev_sim)
                await clock.save(db)
            await manager.broadcast("clock.changed", {"farm_now": next_sim.isoformat()})
            await self._publish(f"Clock jumped to {time_str}")
        elif kind == "wait_completed_cycles":
            _, count, timeout = step
            await self._wait_completed_cycles(count, timeout)
            await self._publish(f"Verified {count} completed cycle(s) with water delivered")
        elif kind == "wait_skipped_cycle":
            _, zone_id, timeout = step
            await self._wait_skipped_cycle(zone_id, timeout)
            await self._publish(f"Verified skipped cycle recorded for {zone_id}")
        else:
            raise ScenarioFailed(f"Unknown step {kind}")

    async def _command(self, ctype, target_type, target_id, payload) -> None:
        async with async_session_factory() as db:
            cmd = await cmd_svc.submit_command(
                db,
                CommandCreate(
                    command_type=ctype,
                    target_type=target_type,
                    target_id=target_id,
                    payload=payload,
                ),
                SCENARIO_ACTOR,
            )
        await self._wait_picked_up(cmd.id)

    async def _wait_picked_up(self, command_id: str) -> None:
        """Wait until the controller has taken the command off the queue.

        Later `wait_zone` steps only trust snapshots pushed after this moment —
        otherwise a stale state from before the command can satisfy them.
        """
        from app.models.command import Command

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.pickup_timeout_s
        while loop.time() < deadline:
            async with async_session_factory() as db:
                cmd = await db.get(Command, command_id)
            if cmd is None or cmd.status != "pending":
                self._picked_up_at = utcnow()
                return
            await asyncio.sleep(self.poll_s / 2)
        raise ScenarioFailed("Controller did not pick up the command (is the simulator running?)")

    async def _wait_zone(self, zone_id: str, states: set[str], timeout: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            async with async_session_factory() as db:
                snap = (await load_snapshots(db)).get(f"zone_{zone_id}")
            fresh = snap is not None and as_utc(snap.updated_at) > self._picked_up_at
            if fresh and snap.state.get("state") in states:
                return
            await asyncio.sleep(self.poll_s)
        raise ScenarioFailed(f"{zone_id} did not reach {sorted(states)} within {timeout}s")

    async def _wait_alarm(self, code: str, timeout: float) -> None:
        from sqlalchemy import and_, or_, select

        from app.services.alarms import OPEN

        started = self._started_farm
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            async with async_session_factory() as db:
                found = (
                    await db.execute(
                        select(Alarm.id).where(
                            Alarm.alarm_code == code,
                            # raised during this run, or still genuinely active
                            # (e.g. ALM-036's 24 h window spans several runs)
                            or_(
                                Alarm.triggered_at >= started,
                                and_(Alarm.status.in_(OPEN), Alarm.cleared_at.is_(None)),
                            ),
                        )
                    )
                ).first()
            if found:
                return
            if loop.time() >= deadline:
                raise ScenarioFailed(f"Expected alarm {code} was not raised within {timeout}s")
            await asyncio.sleep(self.poll_s)

    async def _wait_completed_cycles(self, expected_count: int, timeout: float) -> None:
        from sqlalchemy import select

        from app.models.irrigation_cycle import IrrigationCycle

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            async with async_session_factory() as db:
                res = await db.execute(
                    select(IrrigationCycle).where(
                        IrrigationCycle.outcome == "completed",
                        IrrigationCycle.actual_start_at >= self._started_farm,
                        IrrigationCycle.water_estimate_m3 > 0,
                    )
                )
                if len(res.scalars().all()) >= expected_count:
                    return
            await asyncio.sleep(self.poll_s)
        raise ScenarioFailed(f"Did not see {expected_count} completed cycle(s) within {timeout}s")

    async def _wait_skipped_cycle(self, zone_id: str, timeout: float) -> None:
        from sqlalchemy import select

        from app.models.irrigation_cycle import IrrigationCycle

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            async with async_session_factory() as db:
                res = await db.execute(
                    select(IrrigationCycle).where(
                        IrrigationCycle.zone_id == zone_id,
                        IrrigationCycle.outcome == "skipped",
                        IrrigationCycle.actual_start_at >= self._started_farm,
                    )
                )
                if res.scalars().first():
                    return
            await asyncio.sleep(self.poll_s)
        raise ScenarioFailed(f"Did not see skipped cycle for {zone_id} within {timeout}s")


runner = ScenarioRunner()
