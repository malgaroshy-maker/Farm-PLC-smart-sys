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
    system,
    telemetry,
    websocket,
    zones,
)
from app.services.monitor import Monitor
from app.services.scenarios import runner

log = logging.getLogger("app")


class TokenRedactingFilter(logging.Filter):
    """Redacts tokens across message and arguments on all uvicorn loggers and quiets periodic sync logs."""

    TOKEN_PATTERN = re.compile(r"([?&]?token=|[Bb]earer\s+)[^\s&'\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        # Quiet periodic polling from simulator service account (/state/sync & /commands/pending)
        if record.args:
            args_str = " ".join(str(a) for a in record.args)
            if "/state/sync" in args_str or "/commands/pending" in args_str:
                return False
        if isinstance(record.msg, str):
            if "/state/sync" in record.msg or "/commands/pending" in record.msg:
                return False

        # Redact token query params and Bearer tokens in message
        if isinstance(record.msg, str):
            record.msg = self.TOKEN_PATTERN.sub(r"\1[REDACTED]", record.msg)

        # Redact token query params and Bearer tokens in args
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.TOKEN_PATTERN.sub(r"\1[REDACTED]", a) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (self.TOKEN_PATTERN.sub(r"\1[REDACTED]", v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


def install_token_redacting_filter() -> None:
    redactor = TokenRedactingFilter()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, TokenRedactingFilter) for f in logger.filters):
            logger.addFilter(redactor)


install_token_redacting_filter()


def install_file_logging() -> None:
    """Optional rotating log file (LOG_FILE), so a long-running farm PC never fills its disk."""
    if not settings.log_file:
        return
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    path = Path(settings.log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    handler = RotatingFileHandler(
        path,
        maxBytes=settings.log_file_max_mb * 1024 * 1024,
        backupCount=settings.log_file_backups,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(TokenRedactingFilter())
    root.addHandler(handler)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_token_redacting_filter()
    install_file_logging()
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
    system,
):
    app.include_router(r.router, prefix=API_V1)

app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"message": "Algaroshy Farm Smart Irrigation API", "docs": "/docs", "health": "/health"}
