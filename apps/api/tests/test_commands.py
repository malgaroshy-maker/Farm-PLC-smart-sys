import asyncio
from datetime import timedelta

import httpx
import pytest
from conftest import SIM, ZONE_IDS, login, push_state

from app.core.timeutil import utcnow
from app.main import app

START = {"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"}


def start(client, headers, zone="zone_enab"):
    return client.post("/api/v1/commands", json={**START, "target_id": zone}, headers=headers)


# ── Validation ───────────────────────────────────────────


def test_unknown_command_type_rejected(client):
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "delete_everything", "target_type": "zone", "target_id": "x"},
        headers=login(client, "admin"),
    )
    assert r.status_code == 422


def test_unknown_zone_is_404(client):
    push_state(client)
    assert start(client, login(client, "admin"), zone="zone_nope").status_code == 404


def test_wrong_target_type_is_422(client):
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "start_zone", "target_type": "pump", "target_id": "zone_enab"},
        headers=login(client, "admin"),
    )
    assert r.status_code == 422


def test_set_mode_validates_mode(client):
    admin = login(client, "admin")
    body = {"command_type": "set_mode", "target_type": "system", "payload": {"mode": "turbo"}}
    assert client.post("/api/v1/commands", json=body, headers=admin).status_code == 422
    body["payload"]["mode"] = "manual"
    assert client.post("/api/v1/commands", json=body, headers=admin).status_code == 201


def test_not_implemented_commands_are_explicit(client):
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "force_valve", "target_type": "valve", "target_id": "v"},
        headers=login(client, "admin"),
    )
    assert r.status_code == 422
    assert "not implemented" in r.json()["detail"]


# ── Permissions ──────────────────────────────────────────


def test_viewer_cannot_control(client):
    push_state(client)
    assert start(client, login(client, "viewer")).status_code == 403


def test_operator_can_start_but_not_change_mode(client):
    push_state(client)
    op = login(client, "operator")
    assert start(client, op).status_code == 201
    body = {"command_type": "set_mode", "target_type": "system", "payload": {"mode": "off"}}
    assert client.post("/api/v1/commands", json=body, headers=op).status_code == 403


# ── Interlocks ───────────────────────────────────────────


def test_start_accepted_records_actor_and_event(client):
    push_state(client)
    r = start(client, login(client, "operator"))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["requested_by"] == "user_operator"
    assert body["actor_type"] == "user"


@pytest.mark.parametrize(
    ("state_kwargs", "code"),
    [
        ({"mode": "off"}, "mode_blocks_start"),
        ({"mode": "maintenance"}, "mode_blocks_start"),
        ({"zone_states": {"zone_enab": "running"}}, "zone_already_active"),
        ({"zone_states": {"zone_rumman_1": "running"}}, "max_concurrent_zones"),
        ({"pump_fault": True}, "no_pump_available"),
    ],
)
def test_interlocks_block_start(client, state_kwargs, code):
    push_state(client, **state_kwargs)
    r = start(client, login(client, "operator"))
    assert r.status_code == 409, r.text
    assert r.json()["code"] == code


def test_low_tank_blocks_only_zones_without_direct_well(client):
    push_state(client, tank=5.0)
    op = login(client, "operator")
    r = start(client, op, zone="zone_rumman_1")  # allows_direct_well = False
    assert r.status_code == 409 and r.json()["code"] == "tank_critically_low"
    assert start(client, op, zone="zone_enab").status_code == 201  # allows_direct_well = True


def test_no_live_state_blocks_start(client):
    r = start(client, login(client, "operator"))
    assert r.status_code == 409
    assert r.json()["code"] == "state_stale"


def test_duplicate_pending_start_blocked(client):
    push_state(client)
    op = login(client, "operator")
    assert start(client, op).status_code == 201
    r = start(client, op)
    assert r.status_code == 409 and r.json()["code"] == "duplicate_command"


def test_rejected_command_is_persisted_for_audit(client):
    push_state(client, mode="off")
    op = login(client, "operator")
    cid = start(client, op).json()["command_id"]
    cmds = client.get("/api/v1/commands", headers=op).json()
    rejected = next(c for c in cmds if c["id"] == cid)
    assert rejected["status"] == "rejected"
    assert rejected["failure_reason"].startswith("mode_blocks_start")


def test_stop_is_always_allowed(client):
    push_state(client, mode="off", pump_fault=True)
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "stop_zone", "target_type": "zone", "target_id": "zone_enab"},
        headers=login(client, "operator"),
    )
    assert r.status_code == 201


# ── Simulator round-trip & timeouts ──────────────────────


def test_simulator_picks_up_and_completes(client):
    push_state(client)
    cid = start(client, login(client, "operator")).json()["id"]
    pending = client.get("/api/v1/commands/pending", headers=SIM).json()
    assert [c["id"] for c in pending] == [cid]

    r = client.patch(f"/api/v1/commands/{cid}/sync", json={"status": "completed"}, headers=SIM)
    assert r.status_code == 200 and r.json()["completed_at"]
    assert client.get("/api/v1/commands/pending", headers=SIM).json() == []
    # terminal commands cannot be re-synced
    r = client.patch(f"/api/v1/commands/{cid}/sync", json={"status": "failed"}, headers=SIM)
    assert r.status_code == 409


def test_start_without_duration_carries_the_zone_default(client):
    """G5: the PLC refuses an open-ended start, so the API always sends a duration."""
    push_state(client)
    headers = login(client, "operator")
    start(client, headers)
    zone = client.get("/api/v1/zones/zone_enab", headers=headers).json()
    pending = client.get("/api/v1/commands/pending", headers=SIM).json()
    payload = pending[0]["payload"]
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    assert payload["duration_min"] == zone["default_duration_min"]


def test_invalid_sync_status_rejected(client):
    push_state(client)
    cid = start(client, login(client, "operator")).json()["id"]
    r = client.patch(f"/api/v1/commands/{cid}/sync", json={"status": "done-ish"}, headers=SIM)
    assert r.status_code == 422


def test_stale_pending_commands_time_out(client, monkeypatch):
    push_state(client)
    cid = start(client, login(client, "operator")).json()["id"]
    from app.services import commands as svc

    future = utcnow() + timedelta(seconds=60)
    monkeypatch.setattr(svc, "utcnow", lambda: future)
    assert client.get("/api/v1/commands/pending", headers=SIM).json() == []
    cmds = client.get("/api/v1/commands", headers=login(client, "admin")).json()
    assert next(c for c in cmds if c["id"] == cid)["status"] == "timed_out"


def test_stop_supersedes_orphaned_start(client):
    """Regression: a start the controller never finished blocked every other zone."""
    push_state(client)
    op = login(client, "operator")
    orphan = start(client, op).json()["id"]
    client.patch(f"/api/v1/commands/{orphan}/sync", json={"status": "accepted"}, headers=SIM)
    assert start(client, op, zone="zone_rumman_1").json()["code"] == "max_concurrent_zones"

    r = client.post(
        "/api/v1/commands", json={"command_type": "stop_all", "target_type": "system"}, headers=op
    )
    assert r.status_code == 201
    cmds = {c["id"]: c for c in client.get("/api/v1/commands", headers=op).json()}
    assert cmds[orphan]["status"] == "failed"
    assert cmds[orphan]["failure_reason"] == "Superseded by stop_all"
    assert start(client, op, zone="zone_rumman_1").status_code == 201


def test_stop_zone_only_supersedes_that_zone(client):
    push_state(client)
    op = login(client, "operator")
    keep = start(client, op).json()["id"]
    client.post(
        "/api/v1/commands",
        json={"command_type": "stop_zone", "target_type": "zone", "target_id": "zone_rumman_1"},
        headers=op,
    )
    cmds = {c["id"]: c for c in client.get("/api/v1/commands", headers=op).json()}
    assert cmds[keep]["status"] == "pending"


def test_simultaneous_starts_respect_the_zone_limit(client):
    """Two requests must not both pass the interlocks before either one is saved."""
    push_state(client)
    headers = login(client, "operator")

    async def start_all():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
            return await asyncio.gather(
                *[
                    api.post(
                        "/api/v1/commands",
                        headers=headers,
                        json={
                            "command_type": "start_zone",
                            "target_type": "zone",
                            "target_id": zone_id,
                        },
                    )
                    for zone_id in ZONE_IDS[:4]
                ]
            )

    responses = client.portal.call(start_all)
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]
