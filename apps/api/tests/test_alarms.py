import asyncio
from datetime import timedelta

from conftest import SIM, login, push_state

from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.services.alarms import engine as alarm_engine
from app.services.live_state import load_snapshots

TRIP = {"code": "ALM-005", "device_id": "pump_booster_01"}
NO_FLOW = {"code": "ALM-012", "zone_id": "zone_rumman_2", "value": 0.0, "threshold": 3.0}


def active(client, headers):
    return client.get("/api/v1/alarms", headers=headers).json()


def by_code(alarms, code):
    return next(a for a in alarms if a["alarm_code"] == code)


# ── Lifecycle ────────────────────────────────────────────


def test_plc_condition_creates_one_alarm_with_guidance(client):
    viewer = login(client, "viewer")
    push_state(client, plc_alarms=[TRIP])
    push_state(client, plc_alarms=[TRIP])  # still active → no duplicate
    alarms = active(client, viewer)
    assert [a["alarm_code"] for a in alarms] == ["ALM-005"]
    a = alarms[0]
    assert a["status"] == "active_unacked"
    assert a["severity"] == "S3" and a["condition_active"] is True
    assert a["device_type"] == "pump" and a["source_layer"] == "plc"
    assert a["guidance_ar"] and a["guidance_en"] and a["name_ar"]


def test_latched_alarm_needs_ack_and_reset(client):
    admin, op = login(client, "admin"), login(client, "operator")
    push_state(client, plc_alarms=[TRIP])
    aid = by_code(active(client, op), "ALM-005")["id"]

    # cannot reset while the condition is still true
    assert client.post(f"/api/v1/alarms/{aid}/reset", headers=admin).status_code == 409
    r = client.post(f"/api/v1/alarms/{aid}/ack", headers=op)
    assert r.status_code == 200 and r.json()["status"] == "active_acked"

    push_state(client, plc_alarms=[])  # pump repaired
    a = by_code(active(client, op), "ALM-005")
    assert a["condition_active"] is False and a["status"] == "active_acked"  # latched

    assert client.post(f"/api/v1/alarms/{aid}/reset", headers=op).status_code == 403
    r = client.post(f"/api/v1/alarms/{aid}/reset", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "cleared"
    assert active(client, op) == []


def test_ack_required_alarm_stays_until_acked(client):
    op = login(client, "operator")
    push_state(client, plc_alarms=[NO_FLOW])
    push_state(client, plc_alarms=[])  # condition gone, not acked yet
    a = by_code(active(client, op), "ALM-012")
    assert a["status"] == "active_unacked" and a["condition_active"] is False
    r = client.post(f"/api/v1/alarms/{a['id']}/ack", headers=op)
    assert r.json()["status"] == "cleared"  # no manual reset required


def test_viewer_cannot_ack(client):
    push_state(client, plc_alarms=[NO_FLOW])
    viewer = login(client, "viewer")
    aid = active(client, viewer)[0]["id"]
    assert client.post(f"/api/v1/alarms/{aid}/ack", headers=viewer).status_code == 403


def test_condition_returning_rearms_same_instance(client):
    op = login(client, "operator")
    push_state(client, plc_alarms=[TRIP])
    first = active(client, op)[0]["id"]
    push_state(client, plc_alarms=[])
    push_state(client, plc_alarms=[TRIP])
    alarms = active(client, op)
    assert len(alarms) == 1 and alarms[0]["id"] == first and alarms[0]["condition_active"]


def test_history_keeps_cleared_alarms(client):
    op = login(client, "operator")
    push_state(client, mode="manual")
    push_state(client, mode="auto")
    history = client.get("/api/v1/alarms?view=history", headers=op).json()
    info = by_code(history, "ALM-042")
    assert info["status"] == "cleared" and info["severity"] == "S0"


def test_snapshot_includes_active_alarms(client):
    push_state(client, plc_alarms=[TRIP])
    state = client.get("/api/v1/state/map", headers=login(client, "viewer")).json()
    assert [a["alarm_code"] for a in state["active_alarms"]] == ["ALM-005"]


def test_ws_broadcasts_alarm_active(client):
    push_state(client)
    token = login(client, "viewer")["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.receive_json()  # snapshot
        push_state(client, plc_alarms=[TRIP])
        first, second = ws.receive_json(), ws.receive_json()
        assert first["type"] == "alarm.active"
        assert first["payload"]["alarm_code"] == "ALM-005"
        assert second["type"] == "state.snapshot"
        assert second["payload"]["active_alarms"][0]["alarm_code"] == "ALM-005"


# ── Derived rules ────────────────────────────────────────


def test_tank_low_warning(client):
    op = login(client, "operator")
    push_state(client, tank=20)
    a = by_code(active(client, op), "ALM-001")
    assert a["severity"] == "S1" and a["current_value"] == 20
    push_state(client, tank=60)
    assert active(client, op) == []  # warning: no ack needed, clears by itself


def test_low_pressure_only_while_irrigating(client):
    op = login(client, "operator")
    push_state(client, pressure=0.5)
    assert active(client, op) == []  # nothing running → suppressed
    push_state(client, pressure=0.5, zone_states={"zone_rumman_1": "running"})
    assert by_code(active(client, op), "ALM-008")["threshold_value"] == 1.5


def test_unauthorized_attempt_recorded(client):
    push_state(client)
    viewer = login(client, "viewer")
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
        headers=viewer,
    )
    assert r.status_code == 403
    history = client.get("/api/v1/alarms?view=history", headers=viewer).json()
    a = by_code(history, "ALM-035")
    assert "start_zone" in a["message_en"] and a["zone_id"] == "zone_enab"


def test_repeated_faults_raise_maintenance_alarm(client):
    op = login(client, "operator")
    cond = {"code": "ALM-019", "zone_id": "zone_enab", "device_id": "valve_enab"}
    for _ in range(3):
        push_state(client, plc_alarms=[cond])
        push_state(client, plc_alarms=[])
        aid = by_code(active(client, op), "ALM-019")["id"]
        client.post(f"/api/v1/alarms/{aid}/ack", headers=op)
    push_state(client)
    a = by_code(active(client, op), "ALM-036")
    assert a["zone_id"] == "zone_enab" and a["current_value"] == 3


def test_maintenance_done_clears_repeated_fault_alarm(client):
    op, viewer = login(client, "operator"), login(client, "viewer")
    cond = {"code": "ALM-019", "zone_id": "zone_enab", "device_id": "valve_enab"}
    def fault():
        push_state(client, plc_alarms=[cond])
        push_state(client, plc_alarms=[])
        aid = by_code(active(client, op), "ALM-019")["id"]
        client.post(f"/api/v1/alarms/{aid}/ack", headers=op)

    for _ in range(3):
        fault()
    push_state(client)
    assert by_code(active(client, op), "ALM-036")

    url = "/api/v1/zones/zone_enab/maintenance-done"
    assert client.post(url, headers=viewer).status_code == 403
    assert client.post("/api/v1/zones/nope/maintenance-done", headers=op).status_code == 404
    assert client.post(url, json={"note": "valve replaced"}, headers=op).status_code == 204
    push_state(client)
    assert not [a for a in active(client, op) if a["alarm_code"] == "ALM-036"]
    history = client.get("/api/v1/alarms?view=history", headers=op).json()
    assert by_code(history, "ALM-036")["zone_id"] == "zone_enab"

    # new faults after the sign-off count again from zero
    for _ in range(2):
        fault()
    push_state(client)
    assert not [a for a in active(client, op) if a["alarm_code"] == "ALM-036"]


def test_stale_then_comms_lost_then_recovered(client):
    op = login(client, "operator")
    old = (utcnow() - timedelta(seconds=60)).isoformat()
    push_state(client, updated_at=old)

    async def tick():
        async with async_session_factory() as db:
            await alarm_engine.on_monitor_tick(db, await load_snapshots(db))

    asyncio.run(tick())
    codes = {a["alarm_code"] for a in active(client, op)}
    assert {"ALM-044", "ALM-029"} <= codes
    push_state(client)  # data flows again
    codes = {a["alarm_code"] for a in active(client, op)}
    assert not codes & {"ALM-044", "ALM-029"}


# ── Interlock ────────────────────────────────────────────


def test_open_critical_alarm_blocks_start_until_reset(client):
    admin, op = login(client, "admin"), login(client, "operator")
    body = {"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"}
    push_state(client, plc_alarms=[TRIP])
    r = client.post("/api/v1/commands", json=body, headers=op)
    assert r.status_code == 409 and r.json()["code"] == "critical_alarm_active"

    push_state(client, plc_alarms=[])  # repaired but latched
    assert client.post("/api/v1/commands", json=body, headers=op).status_code == 409
    aid = by_code(active(client, op), "ALM-005")["id"]
    client.post(f"/api/v1/alarms/{aid}/reset", headers=admin)
    assert client.post("/api/v1/commands", json=body, headers=op).status_code == 201


def test_unknown_alarm_404(client):
    assert client.get("/api/v1/alarms/nope", headers=SIM).status_code == 404


def test_repeated_aborted_starts_raise_maintenance_alarm(client):
    """Regression: a stuck valve keeps ONE ALM-019 open, so count aborted starts too."""
    push_state(client)
    op = login(client, "operator")
    for _ in range(3):
        cid = client.post(
            "/api/v1/commands",
            json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
            headers=op,
        ).json()["id"]
        client.patch(
            f"/api/v1/commands/{cid}/sync",
            json={"status": "failed", "failure_reason": "Valve failed to open"},
            headers=SIM,
        )
    push_state(client)
    a = by_code(active(client, op), "ALM-036")
    assert a["zone_id"] == "zone_enab" and a["current_value"] == 3


def test_reset_demo_clears_history_but_keeps_users(client):
    from app.reset_demo import reset_history

    op = login(client, "operator")
    push_state(client, plc_alarms=[{"code": "ALM-019", "zone_id": "zone_enab", "device_id": "valve_enab"}])
    assert active(client, op)
    removed = asyncio.run(reset_history())
    assert removed["alarms"] >= 1
    op = login(client, "operator")  # users survive
    assert client.get("/api/v1/alarms", headers=op).json() == []
    assert client.get("/api/v1/zones", headers=op).json()  # config survives
