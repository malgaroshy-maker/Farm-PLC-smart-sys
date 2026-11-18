"""
Algaroshy Farm — Smart Irrigation System API

FastAPI application entry point.
Run from apps/api:  alembic upgrade head && uvicorn app.main:app --reload --port 8000
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEFAULT_SECRET, settings
from app.routers import (
    alarms,
    auth,
    commands,
    devices,
    farm,
    health,
    sim,
    state,
    telemetry,
    websocket,
    zones,
)
from app.services.monitor import Monitor
from app.services.scenarios import runner

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.check_production_safety()
    if settings.secret_key == DEFAULT_SECRET:
        log.warning("SECRET_KEY is the development default — set a real one before deploying.")
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
for r in (auth, farm, zones, devices, state, commands, alarms, telemetry, sim):
    app.include_router(r.router, prefix=API_V1)

app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"message": "Algaroshy Farm Smart Irrigation API", "docs": "/docs", "health": "/health"}
