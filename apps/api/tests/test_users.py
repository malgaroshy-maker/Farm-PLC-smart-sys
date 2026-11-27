"""User accounts: only the admin manages them, and a changed account is signed out."""

import pytest
from conftest import login
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.models.event_log import EventLog
from app.models.notification import PushSubscription

NEW = {"name": "Salem", "username": " Salem ", "role": "operator", "password": "salem-pass-1"}


def sign_in(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("who", ["operator", "viewer"])
def test_only_the_admin_sees_or_changes_users(client, who):
    headers = login(client, who)
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    assert client.post("/api/v1/users", headers=headers, json=NEW).status_code == 403
    assert (
        client.patch("/api/v1/users/user_admin", headers=headers, json={"name": "x"}).status_code
        == 403
    )


def test_create_change_and_switch_off(client):
    admin = login(client, "admin")
    made = client.post("/api/v1/users", headers=admin, json=NEW)
    assert made.status_code == 201, made.text
    uid = made.json()["id"]
    assert made.json()["username"] == "salem" and "password_hash" not in made.json()
    again = client.post("/api/v1/users", headers=admin, json={**NEW, "username": "SALEM"})
    assert again.status_code == 409
    for bad in ("short", "م" * 37):  # too short; 74 bytes
        r = client.post(
            "/api/v1/users", headers=admin, json={**NEW, "username": "other", "password": bad}
        )
        assert r.status_code == 422, r.text

    session = sign_in(client, "SALEM", "salem-pass-1")
    assert session.status_code == 200, session.text
    salem = bearer(session)

    r = client.patch(f"/api/v1/users/{uid}", headers=admin, json={"role": "viewer"})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/auth/me", headers=salem).status_code == 401

    salem = bearer(sign_in(client, "salem", "salem-pass-1"))
    r = client.patch(f"/api/v1/users/{uid}", headers=admin, json={"is_active": False})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/auth/me", headers=salem).status_code == 401
    assert sign_in(client, "salem", "salem-pass-1").status_code == 401


def test_the_last_admin_cannot_be_removed(client):
    admin = login(client, "admin")
    for change in ({"is_active": False}, {"role": "operator"}):
        r = client.patch("/api/v1/users/user_admin", headers=admin, json=change)
        assert r.status_code == 409 and r.json()["detail"] == "last_admin", r.text
    assert client.get("/api/v1/auth/me", headers=admin).status_code == 200


def test_own_password_needs_the_current_one_and_ends_other_sessions(client):
    first = login(client, "operator")
    url = "/api/v1/auth/password"
    wrong = client.post(
        url, headers=first, json={"current_password": "nope", "new_password": "new-pass-123"}
    )
    assert wrong.status_code == 400, wrong.text
    assert client.get("/api/v1/auth/me", headers=first).status_code == 200
    done = client.post(
        url,
        headers=first,
        json={"current_password": "operator-pass", "new_password": "new-pass-123"},
    )
    assert done.status_code == 200, done.text
    assert client.get("/api/v1/auth/me", headers=first).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(done)).status_code == 200
    assert sign_in(client, "operator", "operator-pass").status_code == 401


def test_a_switched_off_user_loses_the_live_feed_and_phone_alerts(client):
    admin = login(client, "admin")
    token = login(client, "viewer")["Authorization"].split()[1]

    async def subscribe():
        async with async_session_factory() as db:
            db.add(
                PushSubscription(
                    user_id="user_viewer",
                    endpoint="https://push.example/1",
                    p256dh="k",
                    auth="a",
                    created_at=utcnow(),
                )
            )
            await db.commit()

    client.portal.call(subscribe)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "state.snapshot"
        r = client.patch("/api/v1/users/user_viewer", headers=admin, json={"is_active": False})
        assert r.status_code == 200, r.text
        with pytest.raises(WebSocketDisconnect) as closed:
            for _ in range(20):
                ws.receive_json()
        assert closed.value.code == 4401

    async def left():
        async with async_session_factory() as db:
            return (
                list(await db.scalars(select(PushSubscription))),
                list(
                    await db.scalars(
                        select(EventLog.payload_json).where(EventLog.event_type.like("user.%"))
                    )
                ),
            )

    subscriptions, payloads = client.portal.call(left)
    assert subscriptions == []
    assert not any("pass" in (p or "") and "password" not in (p or "") for p in payloads)


@pytest.mark.asyncio
async def test_password_recovery_on_the_farm_pc(client):
    from app.reset_password import reset

    old = login(client, "admin")
    assert await reset("ADMIN", "recovered-pass-1")
    assert not await reset("nobody", "recovered-pass-1")
    assert client.get("/api/v1/auth/me", headers=old).status_code == 401
    assert sign_in(client, "admin", "recovered-pass-1").status_code == 200
