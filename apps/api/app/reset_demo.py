"""
Clear the farm's operating history for a clean demo.

Deletes alarms, commands, the event log, telemetry, device state snapshots
and irrigation cycles. Keeps users (and their passwords), zones, pumps,
valves, sensors, schedules and all configuration.

Run with the API stopped:
    cd apps/api
    python -m app.reset_demo          # or:  run.bat reset  /  ./run.sh reset
"""

import asyncio

from sqlalchemy import delete, func, select

from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.event_log import EventLog
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import DeviceStateSnapshot, TelemetryPoint

HISTORY = [Alarm, Command, EventLog, TelemetryPoint, DeviceStateSnapshot, IrrigationCycle]


async def reset_history() -> dict[str, int]:
    removed: dict[str, int] = {}
    async with async_session_factory() as db:
        for model in HISTORY:
            n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
            await db.execute(delete(model))
            removed[model.__tablename__] = n
        await db.commit()
    return removed


def main() -> None:
    removed = asyncio.run(reset_history())
    print("Demo history cleared:", ", ".join(f"{k} {v}" for k, v in removed.items()))


if __name__ == "__main__":
    main()
