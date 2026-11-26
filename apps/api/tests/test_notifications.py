"""Milestone G3: notification channels — S2/S3 alarms + briefing to Telegram and web push."""

import asyncio
from types import SimpleNamespace

from conftest import login

from app.config import settings
from app.services import notify
from app.services.features import clear_cache


def _flag(client, key, on):
    r = client.put(
        f"/api/v1/system/features/{key}", json={"enabled": on}, headers=login(client, "admin")
    )
    assert r.status_code == 200


def test_only_major_and_critical_alarms_notify():
    mk = lambda sev: SimpleNamespace(  # noqa: E731
        severity=sev,
        alarm_code="ALM-012",
        message_ar="لا تدفق",
        message_en="No flow",
        zone_id="zone_rumman_2",
        device_id=None,
        guidance_ar="افحص الصمام",
    )
    assert notify.alarm_notification(mk("S1")) is None
    n = notify.alarm_notification(mk("S3"))
    assert n and n.severity == "S3" and "ALM-012" in n.title_ar and "zone_rumman_2" in n.body_ar


def test_dispatch_sends_to_enabled_configured_channels(client, monkeypatch):
    sent = []

    async def fake_telegram(n, chat_id):
        sent.append((n.title_ar, chat_id))
        return True

    monkeypatch.setattr(notify, "send_telegram", fake_telegram)
    monkeypatch.setattr(settings, "telegram_bot_token", "x")
    h = login(client, "admin")
    try:
        assert (
            client.put(
                "/api/v1/system/notifications/telegram", json={"chat_id": "12345"}, headers=h
            ).status_code
            == 200
        )
        # switched off by default: nothing is sent
        clear_cache()
        assert asyncio.run(notify.dispatch(notify.Notification("test", "س", "t"))) == {}
        _flag(client, "notify.telegram", True)
        clear_cache()
        r = client.post("/api/v1/system/notifications/test", headers=h).json()
        assert r["result"]["telegram"] is True and sent[-1][1] == "12345"
        status = client.get("/api/v1/system/notifications", headers=h).json()
        assert status["telegram"]["configured"] is True and status["severities"] == ["S3", "S2"]
    finally:
        _flag(client, "notify.telegram", False)
        clear_cache()


def test_web_push_keys_are_stable_and_subscriptions_saved(client):
    h = login(client, "viewer")
    k1 = client.get("/api/v1/system/push/public-key", headers=h).json()["public_key"]
    k2 = client.get("/api/v1/system/push/public-key", headers=h).json()["public_key"]
    assert k1 == k2 and len(k1) > 80
    sub = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
        "keys": {"p256dh": "p", "auth": "a"},
    }
    assert client.post("/api/v1/system/push/subscribe", json=sub, headers=h).json() == {"ok": True}
    status = client.get("/api/v1/system/notifications", headers=login(client, "admin")).json()
    assert status["web_push"]["devices"] >= 1
    assert client.post("/api/v1/system/push/unsubscribe", json=sub, headers=h).json() == {
        "ok": True
    }


def test_telegram_detect_needs_a_token(client, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    r = client.post("/api/v1/system/notifications/telegram/detect", headers=login(client, "admin"))
    assert r.status_code == 409 and "telegram_token_missing" in r.text
