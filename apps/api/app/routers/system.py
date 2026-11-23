"""System health — /api/v1/system/health (Milestone G1).

One call answers "is everything working?" for the Live badge and its health panel.
Each check is ok | warn | fail with a machine-readable `code` the UI translates
(AR/EN) into what is wrong and what to do. Paths and disk details are admin-only.
"""

import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import _is_sqlite, get_db
from app.deps import Actor, get_actor
from app.services.ai.agent import is_primary_degraded
from app.services.live_state import last_update, load_snapshots
from app.services.monitor import MONITOR_STATUS
from app.services.weather import weather_service

router = APIRouter(prefix="/system", tags=["System"])

VERSION = "0.4.0"
STARTED_AT = time.time()


def _check(key: str, status: str, code: str, **detail: Any) -> dict[str, Any]:
    return {"key": key, "status": status, "code": code, "detail": detail}


def _db_path() -> Path | None:
    if not _is_sqlite:
        return None
    raw = settings.database_url.split("///", 1)[-1]
    return Path(raw) if raw and raw != ":memory:" else None


@router.get("/health")
async def system_health(actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    is_admin = actor.is_service or actor.role == "owner_admin"
    checks: list[dict[str, Any]] = []

    # 1. database: reachable and quick
    t0 = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        journal = None
        if _is_sqlite:
            journal = (await db.execute(text("PRAGMA journal_mode"))).scalar()
        status = "ok" if ms < 200 else "warn"
        checks.append(
            _check(
                "database", status, "db_ok" if status == "ok" else "db_slow", ms=ms, journal=journal
            )
        )
    except Exception:  # pragma: no cover - DB down means this request barely works
        checks.append(_check("database", "fail", "db_down"))

    # 2. live link to the controller (simulator now, PLC later): age of the newest state
    snapshots = await load_snapshots(db)
    last = last_update(snapshots)
    age = round((utcnow() - last).total_seconds(), 1) if last else None
    stale_after = settings.state_stale_after_sec
    if age is None:
        checks.append(_check("controller", "fail", "link_never", source=settings.controller_mode))
    elif age <= stale_after:
        checks.append(
            _check("controller", "ok", "link_ok", age_sec=age, source=settings.controller_mode)
        )
    else:
        checks.append(
            _check(
                "controller",
                "fail",
                "link_stale",
                age_sec=age,
                stale_after_sec=stale_after,
                source=settings.controller_mode,
            )
        )

    # 3. monitor + scheduler loop heartbeat
    last_ok = MONITOR_STATUS.get("last_ok")
    loop_age = round(time.time() - last_ok, 1) if last_ok else None
    if loop_age is None:
        checks.append(_check("scheduler", "warn", "loop_starting"))
    elif loop_age > max(10.0, settings.monitor_interval_sec * 10):
        checks.append(
            _check(
                "scheduler",
                "fail",
                "loop_stuck",
                age_sec=loop_age,
                failures=MONITOR_STATUS["failures"],
            )
        )
    elif MONITOR_STATUS["failures"]:
        checks.append(
            _check("scheduler", "warn", "loop_errors", failures=MONITOR_STATUS["failures"])
        )
    else:
        checks.append(
            _check("scheduler", "ok", "loop_ok", age_sec=loop_age, farm_speed=clock.speed)
        )

    # 4. AI provider (rule-based fallback always works, so degraded = warn, never fail)
    if is_primary_degraded():
        checks.append(_check("ai", "warn", "ai_degraded"))
    else:
        checks.append(_check("ai", "ok", "ai_ok"))

    # 5. weather forecast
    w = weather_service.health()
    wstatus = {"healthy": "ok", "degraded": "warn"}.get(w.get("status"), "warn")
    checks.append(_check("weather", wstatus, f"weather_{w.get('status', 'unknown')}"))

    # 6. disk space where the database lives
    path = _db_path()
    try:
        usage = shutil.disk_usage((path.parent if path else Path(".")).resolve())
        free_gb = round(usage.free / 1e9, 1)
        dstatus = "ok" if free_gb >= 2 else "warn" if free_gb >= 0.5 else "fail"
        detail: dict[str, Any] = {"free_gb": free_gb}
        if is_admin and path and path.exists():
            detail["db_mb"] = round(path.stat().st_size / 1e6, 1)
            detail["db_path"] = str(path)
        if is_admin and settings.log_file:
            detail["log_file"] = settings.log_file
        checks.append(_check("disk", dstatus, f"disk_{dstatus}", **detail))
    except OSError:  # pragma: no cover
        checks.append(_check("disk", "warn", "disk_unknown"))

    order = {"ok": 0, "warn": 1, "fail": 2}
    overall = max((c["status"] for c in checks), key=order.__getitem__)
    return {
        "status": overall,
        "version": VERSION,
        "uptime_sec": round(time.time() - STARTED_AT),
        "checked_at": utcnow().isoformat(),
        "checks": checks,
    }
