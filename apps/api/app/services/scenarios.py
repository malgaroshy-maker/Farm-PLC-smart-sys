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


class ScenarioRunner:
    def __init__(self) -> None:
        self.state = RunState()
        self._task: asyncio.Task | None = None
        self._started = utcnow()
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

        started = self._started
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


runner = ScenarioRunner()
