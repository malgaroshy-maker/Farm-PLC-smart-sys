"""
Algaroshy Farm — Smart Irrigation System API

FastAPI application entry point with CORS, versioned routers, and lifespan management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import farm, zones, devices, health, state, commands, websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — create tables on startup (dev only)."""
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Algaroshy Farm Smart Irrigation API",
    description="PLC-driven, AI-enhanced smart irrigation control system",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────

# Health (no prefix)
app.include_router(health.router)

# API v1
API_V1 = "/api/v1"
app.include_router(farm.router, prefix=API_V1)
app.include_router(zones.router, prefix=API_V1)
app.include_router(devices.router, prefix=API_V1)
app.include_router(state.router, prefix=API_V1)
app.include_router(commands.router, prefix=API_V1)

# WebSockets
app.include_router(websocket.router)


@app.get("/")
async def root():
    """Root redirect to API docs."""
    return {
        "message": "Algaroshy Farm Smart Irrigation API",
        "docs": "/docs",
        "health": "/health",
    }
