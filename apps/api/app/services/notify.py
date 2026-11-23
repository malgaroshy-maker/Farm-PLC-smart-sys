"""Notification channels (Milestone G3).

One dispatcher, several channels. Each channel is switched on/off on the Settings page
(feature switches `notify.*`) and only sends when it is configured.

Channels
  - in_app    the live alarm chime / fly-to in the web app (handled in the browser)
  - telegram  a bot message to the owner's chat (token in .env, chat id saved here)
  - web_push  phone/desktop push from the installed app (VAPID keys generated once)

What is sent (owner, 2026-11-23): new S3 critical and S2 major alarms, and the daily
briefing. Sending never blocks or breaks the alarm path.
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.models.notification import NotificationSettings, PushSubscription
from app.services.features import is_enabled

log = logging.getLogger(__name__)

NOTIFY_SEVERITIES = {"S2", "S3"}
TELEGRAM_API = "https://api.telegram.org"


@dataclass
class Notification:
    kind: str  # alarm | briefing | test
    title_ar: str
    title_en: str
    body_ar: str = ""
    body_en: str = ""
    severity: str | None = None
    url: str = "/"


# ── settings ────────────────────────────────────────────────


async def get_settings_row(db: AsyncSession) -> NotificationSettings:
    row = await db.get(NotificationSettings, "default")
    if row is None:
        row = NotificationSettings(id="default")
        db.add(row)
        await db.flush()
    return row


def telegram_configured() -> bool:
    return bool(settings.telegram_bot_token)


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


async def vapid_keys(db: AsyncSession) -> tuple[str, str]:
    """(public, private) — from .env, or generated once and stored."""
    if settings.vapid_public_key and settings.vapid_private_key:
        return settings.vapid_public_key, settings.vapid_private_key
    row = await get_settings_row(db)
    if not (row.vapid_public_key and row.vapid_private_key):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = ec.generate_private_key(ec.SECP256R1())
        priv = key.private_numbers().private_value.to_bytes(32, "big")
        pub = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        row.vapid_private_key = _b64url(priv)
        row.vapid_public_key = _b64url(pub)
        row.updated_at = utcnow()
        await db.commit()
    return row.vapid_public_key, row.vapid_private_key


# ── channels ────────────────────────────────────────────────


def _telegram_text(n: Notification) -> str:
    icon = {"S3": "🚨", "S2": "⚠️"}.get(n.severity or "", "🌿")
    parts = [f"{icon} <b>{n.title_ar}</b>"]
    if n.body_ar:
        parts.append(n.body_ar)
    parts.append(f"<i>{n.title_en}</i>")
    return "\n".join(parts)[:4000]


async def send_telegram(n: Notification, chat_id: str) -> bool:
    if not telegram_configured() or not chat_id:
        return False
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            url, json={"chat_id": chat_id, "text": _telegram_text(n), "parse_mode": "HTML"}
        )
    if r.status_code != 200:
        log.warning("Telegram send failed: HTTP %s", r.status_code)  # never log the token/url
        return False
    return True


async def telegram_detect_chat() -> str | None:
    """Chat id of the latest message sent to the bot (owner sends /start first)."""
    if not telegram_configured():
        return None
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/getUpdates"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url)
    if r.status_code != 200:
        return None
    updates = r.json().get("result") or []
    for u in reversed(updates):
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            return str(chat["id"])
    return None


async def send_web_push(db: AsyncSession, n: Notification) -> int:
    subs = (await db.execute(select(PushSubscription))).scalars().all()
    if not subs:
        return 0
    from pywebpush import WebPushException, webpush

    _pub, priv = await vapid_keys(db)
    payload = json.dumps(
        {
            "title": n.title_ar,
            "body": n.body_ar or n.title_en,
            "url": n.url,
            "tag": n.kind,
            "severity": n.severity,
        },
        ensure_ascii=False,
    )
    sent = 0
    for s in subs:
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": s.endpoint,
                    "keys": {"p256dh": s.p256dh, "auth": s.auth},
                },
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=3600,
            )
            s.last_ok_at = utcnow()
            s.failures = 0
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):  # browser unsubscribed: forget it
                await db.delete(s)
            else:
                s.failures = (s.failures or 0) + 1
                log.warning("web push failed (HTTP %s)", status)
        except Exception as exc:  # pragma: no cover
            s.failures = (s.failures or 0) + 1
            log.warning("web push error: %s", type(exc).__name__)
    await db.commit()
    return sent


# ── dispatcher ──────────────────────────────────────────────


async def dispatch(n: Notification, db: AsyncSession | None = None) -> dict[str, object]:
    """Send to every enabled + configured channel. Returns what happened (for tests / test button)."""
    result: dict[str, object] = {}

    async def run(session: AsyncSession) -> None:
        if await is_enabled(session, "notify.telegram"):
            row = await get_settings_row(session)
            try:
                result["telegram"] = await send_telegram(n, row.telegram_chat_id or "")
            except Exception as exc:
                log.warning("telegram error: %s", type(exc).__name__)
                result["telegram"] = False
        if await is_enabled(session, "notify.web_push"):
            try:
                result["web_push"] = await send_web_push(session, n)
            except Exception as exc:
                log.warning("web push dispatch error: %s", type(exc).__name__)
                result["web_push"] = 0

    if db is not None:
        await run(db)
    else:
        async with async_session_factory() as session:
            await run(session)
    return result


def notify_in_background(n: Notification) -> None:
    """Fire-and-forget from hot paths (alarm engine); errors are logged, never raised."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover
        return
    task = loop.create_task(dispatch(n))
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


_BACKGROUND: set[asyncio.Task] = set()


def alarm_notification(alarm) -> Notification | None:
    if alarm.severity not in NOTIFY_SEVERITIES:
        return None
    from app.core.alarm_catalog import CATALOG

    spec = CATALOG.get(alarm.alarm_code)
    name_ar = getattr(spec, "name_ar", None) or alarm.message_ar or alarm.alarm_code
    name_en = getattr(spec, "name", None) or alarm.message_en or alarm.alarm_code
    where = alarm.zone_id or alarm.device_id or ""
    return Notification(
        kind="alarm",
        severity=alarm.severity,
        title_ar=f"{alarm.alarm_code} — {name_ar}",
        title_en=f"{alarm.alarm_code} — {name_en}",
        body_ar=" · ".join(x for x in (where, alarm.guidance_ar or "") if x)[:300],
        body_en=where,
        url="/alarms",
    )
