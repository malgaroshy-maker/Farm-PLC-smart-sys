"""Background loop: command timeouts, stale-data alarms, telemetry retention."""

import asyncio
import logging

from app.config import settings
from app.database import async_session_factory
from app.services.alarms import engine as alarm_engine
from app.services.commands import expire_stale_commands
from app.services.live_state import current_map_state, is_fresh, load_snapshots
from app.services.realtime import manager
from app.services.telemetry import prune_old

log = logging.getLogger(__name__)
PRUNE_EVERY_TICKS = 3600


class Monitor:
    def __init__(self) -> None:
        self._was_fresh: bool | None = None
        self._ticks = 0

    async def tick(self) -> None:
        self._ticks += 1
        async with async_session_factory() as db:
            await expire_stale_commands(db)
            snapshots = await load_snapshots(db)
            await alarm_engine.on_monitor_tick(db, snapshots)
            fresh = is_fresh(snapshots)
            if self._was_fresh and not fresh:
                await manager.broadcast("telemetry.stale", {})
                await manager.broadcast("state.snapshot", await current_map_state(db))
            if self._ticks % PRUNE_EVERY_TICKS == 1:
                await prune_old(db)
        self._was_fresh = fresh

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # keep monitoring even if one tick fails
                log.exception("monitor tick failed")
            await asyncio.sleep(settings.monitor_interval_sec)
