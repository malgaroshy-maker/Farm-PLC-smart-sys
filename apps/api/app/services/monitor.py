"""Background loop: expires stuck commands and announces stale telemetry."""

import asyncio
import logging

from app.config import settings
from app.database import async_session_factory
from app.services.commands import expire_stale_commands
from app.services.live_state import build_map_state, is_fresh, load_snapshots
from app.services.realtime import manager

log = logging.getLogger(__name__)


class Monitor:
    def __init__(self) -> None:
        self._was_fresh: bool | None = None

    async def tick(self) -> None:
        async with async_session_factory() as db:
            await expire_stale_commands(db)
            snapshots = await load_snapshots(db)
        fresh = is_fresh(snapshots)
        if self._was_fresh and not fresh:
            await manager.broadcast("telemetry.stale", {"last_snapshot_ts": None})
            await manager.broadcast("state.snapshot", build_map_state(snapshots))
        self._was_fresh = fresh

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # keep monitoring even if one tick fails
                log.exception("monitor tick failed")
            await asyncio.sleep(settings.monitor_interval_sec)
