"""
Clear the farm's operating history for a clean demo.

Deletes alarms, commands, the event log, telemetry, device state snapshots
and irrigation cycles. Keeps users (and their passwords), zones, pumps,
valves, sensors, schedules, programs, program steps and all configuration.

Run with the API stopped:
    cd apps/api
    python -m app.reset_demo          # or:  run.bat reset  /  ./run.sh reset
"""

import asyncio

from sqlalchemy import delete, func, select

from app.core.clock import clock
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.event_log import EventLog
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program, SchedulerState
from app.models.telemetry import DeviceStateSnapshot, TelemetryPoint

# Operating history models to clear.
# Note: Programs and program_steps are intentionally preserved: they represent configured
# farm irrigation automation logic and schedules. A demo reset clears only transient
# operating history (cycles, telemetry_points, event_log, alarms).
HISTORY = [
    Alarm,
    Command,
    EventLog,
    TelemetryPoint,
    DeviceStateSnapshot,
    IrrigationCycle,
    SchedulerState,
]


async def reset_history() -> dict[str, int]:
    from app.services.scheduler import scheduler
    from app.services.telemetry import recorder

    recorder._last_farm = None
    recorder._last_real = None
    scheduler.reset()
    removed: dict[str, int] = {}
    async with async_session_factory() as db:
        # Query and display enabled programs that are preserved
        prog_stmt = select(Program.name).where(Program.enabled.is_(True)).order_by(Program.name)
        enabled_programs = list((await db.execute(prog_stmt)).scalars().all())
        if enabled_programs:
            print(f"Preserving enabled programs: {', '.join(enabled_programs)}")
        else:
            print("Preserving enabled programs: (none)")

        for model in HISTORY:
            n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
            await db.execute(delete(model))
            removed[model.__tablename__] = n
        clock.reset_to_real()
        await clock.save(db)
        await db.commit()
    return removed


def main() -> None:
    removed = asyncio.run(reset_history())
    print("Demo history cleared:", ", ".join(f"{k} {v}" for k, v in removed.items()))


if __name__ == "__main__":
    main()
