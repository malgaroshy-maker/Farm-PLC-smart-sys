"""Regression tests for the 2026-11-27 security audit."""

from datetime import timedelta

import pytest
from conftest import login, push_state

from app.core.timeutil import utcnow
from app.services import login_throttle
from app.services.notify import Notification, _telegram_text
from app.services.push_endpoint import is_push_service_url

KEYS = {"p256dh": "p", "auth": "a"}
DEVICE = "https://fcm.googleapis.com/fcm/send/abc"


def _sign_in(client, password):
    return client.post("/api/v1/auth/login", json={"username": "admin", "password": password})


def test_wrong_passwords_pause_sign_in_then_recover(client, monkeypatch):
    for n in range(login_throttle.MAX_FAILURES):
        assert _sign_in(client, f"wrong-{n}").status_code == 401
    blocked = _sign_in(client, "admin-pass")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0

    later = login_throttle.time.monotonic() + login_throttle.WINDOW_SEC + 1
    monkeypatch.setattr(login_throttle.time, "monotonic", lambda: later)
    assert _sign_in(client, "admin-pass").status_code == 200


def test_correct_password_clears_the_count_and_failures_are_logged(client):
    for _ in range(login_throttle.MAX_FAILURES - 1):
        _sign_in(client, "wrong")
    assert _sign_in(client, "admin-pass").status_code == 200
    assert _sign_in(client, "wrong").status_code == 401
    events = client.get("/api/v1/events?category=user", headers=login(client, "admin")).json()
    assert [e["event_type"] for e in events].count(
        "user.login_failed"
    ) == login_throttle.MAX_FAILURES


@pytest.mark.parametrize(
    "url",
    [
        "http://fcm.googleapis.com/x",
        "https://127.0.0.1/internal",
        "https://192.168.0.1/",
        "https://fcm.googleapis.com.evil.test/x",
        "https://evilfcm.googleapis.com/x",
        "https://user@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",
        "https://127.0.0.1\\@fcm.googleapis.com/x",
        "https://[broken",
    ],
)
def test_other_addresses_are_not_push_services(url):
    assert not is_push_service_url(url)


@pytest.mark.parametrize(
    "url",
    [
        DEVICE,
        "https://updates.push.services.mozilla.com/wpush/v2/x",
        "https://web.push.apple.com/x",
        "https://wns2-am3p.notify.windows.com/w/?token=x",
    ],
)
def test_browser_push_services_are_accepted(url):
    assert is_push_service_url(url)


def test_push_subscriptions_are_checked_and_private(client):
    viewer, operator = login(client, "viewer"), login(client, "operator")

    def call(action, headers, endpoint=DEVICE):
        return client.post(
            f"/api/v1/system/push/{action}",
            headers=headers,
            json={"endpoint": endpoint, "keys": KEYS},
        )

    def devices():
        r = client.get("/api/v1/system/notifications", headers=login(client, "admin"))
        return r.json()["web_push"]["devices"]

    assert call("subscribe", viewer, "http://127.0.0.1:9/internal").status_code == 422
    assert call("subscribe", viewer).status_code == 200
    call("unsubscribe", operator)
    assert devices() == 1
    call("unsubscribe", viewer)
    assert devices() == 0


def test_telegram_text_is_escaped():
    text = _telegram_text(Notification("briefing", "a<b", "c&d", body_ar="flow < 2 & rising"))
    assert "flow &lt; 2 &amp; rising" in text
    assert "<b>a&lt;b</b>" in text and "<i>c&amp;d</i>" in text


def test_live_data_recovers_after_a_clock_is_set_back(client):
    headers = login(client, "operator")
    push_state(client, updated_at=(utcnow() + timedelta(hours=2)).isoformat())
    assert client.get("/api/v1/state/map", headers=headers).json()["data_fresh"] is False
    push_state(client)
    assert client.get("/api/v1/state/map", headers=headers).json()["data_fresh"] is True
