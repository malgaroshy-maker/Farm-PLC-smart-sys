"""System health — /api/v1/system/health (Milestone G1).

One call answers "is everything working?" for the Live badge and its health panel.
Each check is ok | warn | fail with a machine-readable `code` the UI translates
(AR/EN) into what is wrong and what to do. Paths and disk details are admin-only.
"""

import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import _is_sqlite, get_db
from app.deps import Actor, get_actor, require_admin
from app.services import backup
from app.services.ai.agent import is_primary_degraded
from app.services.live_state import last_update, load_snapshots
from app.services.monitor import MONITOR_STATUS
from app.services.push_endpoint import is_push_service_url
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
    last = last_update(snapshots, controller_only=True)
    age = (utcnow() - last).total_seconds() if last else None
    stale_after = settings.state_stale_after_sec
    if age is None:
        checks.append(_check("controller", "fail", "link_never", source=settings.controller_mode))
    elif 0 <= age <= stale_after:
        checks.append(
            _check(
                "controller",
                "ok",
                "link_ok",
                age_sec=round(age, 1),
                source=settings.controller_mode,
            )
        )
    else:
        checks.append(
            _check(
                "controller",
                "fail",
                "link_stale",
                age_sec=round(age, 1),
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

    # 7. the daily backup (a failure must not stay silent)
    if backup.db_path() is not None:
        code = backup.health_code(time.time() - STARTED_AT)
        checks.append(_check("backup", "ok" if code == "backup_ok" else "warn", code))

    order = {"ok": 0, "warn": 1, "fail": 2}
    overall = max((c["status"] for c in checks), key=order.__getitem__)
    return {
        "status": overall,
        "version": VERSION,
        "uptime_sec": round(time.time() - STARTED_AT),
        "checked_at": utcnow().isoformat(),
        "checks": checks,
    }


# ── Feature switches (Milestone G3) ──────────────────────────


class FeatureUpdate(BaseModel):
    enabled: bool


@router.get("/features")
async def list_features(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    """All feature switches with their group (any signed-in user: the web hides switched-off UI)."""
    from app.services.features import FEATURES, all_features

    values = await all_features(db)
    return {
        "features": values,
        "groups": {k: g for k, (_d, g) in FEATURES.items()},
        "defaults": {k: d for k, (d, _g) in FEATURES.items()},
    }


@router.put("/features/{key}")
async def update_feature(
    key: str,
    body: FeatureUpdate,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.events import log_event
    from app.services.features import UnknownFeature, set_feature
    from app.services.realtime import manager

    try:
        values = await set_feature(db, key, body.enabled, actor.actor_id)
    except UnknownFeature:
        raise HTTPException(404, f"unknown feature '{key}'") from None
    await log_event(
        db,
        "system.feature_changed",
        "feature",
        key,
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"key": key, "enabled": body.enabled},
    )
    await db.commit()
    await manager.broadcast("features.updated", {"features": values})
    return {"features": values}


# ── Notifications (Milestone G3) ─────────────────────────────


async def _log_telegram(db: AsyncSession, actor: Actor, action: str) -> None:
    from app.services.events import log_event

    await log_event(  # the chat id itself is not written: every user can read the log
        db,
        "notify.settings_changed",
        "notification",
        "telegram",
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"action": action},
    )


class TelegramChat(BaseModel):
    chat_id: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict[str, str]


@router.get("/notifications")
async def notification_status(
    _: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import func
    from sqlalchemy import select as _select

    from app.models.notification import PushSubscription
    from app.services.features import all_features
    from app.services.notify import get_settings_row, telegram_configured

    row = await get_settings_row(db)
    await db.commit()
    flags = await all_features(db)
    subs = (await db.execute(_select(func.count()).select_from(PushSubscription))).scalar()
    return {
        "in_app": {"enabled": flags["notify.in_app"], "configured": True},
        "telegram": {
            "enabled": flags["notify.telegram"],
            "configured": telegram_configured() and bool(row.telegram_chat_id),
            "token_set": telegram_configured(),
            "chat_id": row.telegram_chat_id,
        },
        "web_push": {
            "enabled": flags["notify.web_push"],
            "configured": bool(subs),
            "devices": subs,
        },
        "severities": ["S3", "S2"],
    }


@router.post("/notifications/telegram/detect")
async def telegram_detect(
    actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """After the owner sends /start to the bot, read the chat id from the bot's updates."""
    from app.core.timeutil import utcnow as _now
    from app.services.notify import (
        SeveralChats,
        get_settings_row,
        telegram_configured,
        telegram_detect_chat,
    )

    if not telegram_configured():
        raise HTTPException(409, "telegram_token_missing")
    try:
        chat_id = await telegram_detect_chat()
    except SeveralChats:
        # the newest sender could be a stranger who found the bot: the owner types the id
        raise HTTPException(409, "telegram_several_chats") from None
    if not chat_id:
        raise HTTPException(404, "telegram_no_message")
    row = await get_settings_row(db)
    row.telegram_chat_id = chat_id
    row.updated_at = _now()
    await _log_telegram(db, actor, "chat_detected")
    await db.commit()
    return {"chat_id": chat_id}


@router.put("/notifications/telegram")
async def telegram_set_chat(
    body: TelegramChat, actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    from app.core.timeutil import utcnow as _now
    from app.services.notify import get_settings_row

    row = await get_settings_row(db)
    row.telegram_chat_id = body.chat_id.strip() or None
    row.updated_at = _now()
    await _log_telegram(db, actor, "chat_set" if row.telegram_chat_id else "chat_removed")
    await db.commit()
    return {"chat_id": row.telegram_chat_id}


@router.post("/notifications/test")
async def notification_test(_: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.services.notify import Notification, dispatch

    result = await dispatch(
        Notification(
            kind="test",
            title_ar="رسالة تجريبية من نظام الري",
            title_en="Test message from the irrigation system",
            body_ar="إذا وصلتك هذه الرسالة فالتنبيهات تعمل.",
            body_en="If you got this, notifications work.",
        ),
        db,
    )
    return {"result": result}


@router.get("/push/public-key")
async def push_public_key(_: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)):
    from app.services.notify import vapid_keys

    pub, _priv = await vapid_keys(db)
    return {"public_key": pub}


@router.post("/push/subscribe")
async def push_subscribe(
    body: PushSubscriptionIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select as _select

    from app.core.timeutil import utcnow as _now
    from app.models.notification import PushSubscription

    if not body.keys.get("p256dh") or not body.keys.get("auth"):
        raise HTTPException(422, "subscription keys missing")
    if not is_push_service_url(body.endpoint):
        raise HTTPException(422, "not a browser push service address")
    row = (
        await db.execute(
            _select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
        )
    ).scalar_one_or_none()
    if row is None:
        row = PushSubscription(
            endpoint=body.endpoint,
            p256dh=body.keys["p256dh"],
            auth=body.keys["auth"],
            created_at=_now(),
        )
        db.add(row)
    row.user_id = actor.actor_id
    row.p256dh, row.auth = body.keys["p256dh"], body.keys["auth"]
    await db.commit()
    return {"ok": True}


@router.post("/push/unsubscribe")
async def push_unsubscribe(
    body: PushSubscriptionIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import delete as _delete

    from app.models.notification import PushSubscription

    query = _delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    if actor.role != "owner_admin":  # only your own devices
        query = query.where(PushSubscription.user_id == actor.actor_id)
    await db.execute(query)
    await db.commit()
    return {"ok": True}
