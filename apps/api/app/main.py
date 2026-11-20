"""
Algaroshy Farm — Smart Irrigation System API

FastAPI application entry point.
Run from apps/api:  alembic upgrade head && uvicorn app.main:app --reload --port 8000
"""

import asyncio
import contextlib
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEFAULT_SECRET, settings
from app.core.clock import clock
from app.database import async_session_factory
from app.routers import (
    ai,
    alarms,
    auth,
    commands,
    cycles,
    devices,
    events,
    farm,
    health,
    reports,
    schedules,
    sim,
    state,
    telemetry,
    websocket,
    zones,
)
from app.services.monitor import Monitor
from app.services.scenarios import runner

log = logging.getLogger("app")


class TokenRedactingFilter(logging.Filter):
    """Redacts ?token=<anything> query parameters in uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = re.sub(r"\?token=[^\s&'\"]+", "?token=[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    re.sub(r"\?token=[^\s&'\"]+", "?token=[REDACTED]", a)
                    if isinstance(a, str)
                    else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (
                        re.sub(r"\?token=[^\s&'\"]+", "?token=[REDACTED]", v)
                        if isinstance(v, str)
                        else v
                    )
                    for k, v in record.args.items()
                }
        return True


def install_token_redacting_filter() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, TokenRedactingFilter) for f in access_logger.filters):
        access_logger.addFilter(TokenRedactingFilter())


install_token_redacting_filter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_token_redacting_filter()
    settings.check_production_safety()
    if settings.secret_key == DEFAULT_SECRET:
        log.warning("SECRET_KEY is the development default — set a real one before deploying.")
    async with async_session_factory() as db:
        await clock.load(db)
        from app.services.scenarios import cleanup_scenario_programs

        cleaned = await cleanup_scenario_programs(db)
        if cleaned:
            log.info("Cleaned up %d leftover scenario program(s) on startup", cleaned)
    task = asyncio.create_task(Monitor().run())
    try:
        yield
    finally:
        await runner.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Algaroshy Farm Smart Irrigation API",
    description="PLC-driven smart irrigation control system",
    version="0.2.0",
    lifespan=lifespan,
)

# Bearer tokens (not cookies) → credentials are not needed for CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)

API_V1 = "/api/v1"
for r in (
    auth,
    farm,
    zones,
    devices,
    state,
    commands,
    alarms,
    telemetry,
    sim,
    events,
    schedules,
    cycles,
    reports,
    ai,
):
    app.include_router(r.router, prefix=API_V1)

app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"message": "Algaroshy Farm Smart Irrigation API", "docs": "/docs", "health": "/health"}
