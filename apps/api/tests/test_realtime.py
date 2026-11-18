import pytest
from conftest import SIM, login, push_state
from starlette.websockets import WebSocketDisconnect


def _token(client, user="viewer"):
    return login(client, user)["Authorization"].split()[1]


def test_ws_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


def test_ws_sends_snapshot_then_change_events(client):
    push_state(client)
    with client.websocket_connect(f"/ws?token={_token(client)}") as ws:
        first = ws.receive_json()
        assert first["type"] == "state.snapshot"
        assert len(first["payload"]["zones"]) == 12
        assert first["payload"]["data_fresh"] is True
        assert "ts" in first

        push_state(client, zone_states={"zone_enab": "running"})
        changed = ws.receive_json()
        assert changed["type"] == "zone.state.changed"
        assert changed["payload"] == {
            **changed["payload"],
            "zone_id": "zone_enab",
            "previous_state": "off",
            "current_state": "running",
        }
        # running at 0 bar also (correctly) raises the low-pressure warning
        rest = [ws.receive_json()["type"] for _ in range(2)]
        assert rest == ["alarm.active", "state.snapshot"]


def test_ws_broadcasts_command_updates(client):
    push_state(client)
    with client.websocket_connect(f"/ws?token={_token(client)}") as ws:
        ws.receive_json()  # snapshot
        r = client.post(
            "/api/v1/commands",
            json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
            headers=login(client, "operator"),
        )
        msg = ws.receive_json()
        assert msg["type"] == "command.updated"
        assert msg["payload"]["id"] == r.json()["id"]


def test_state_map_reports_staleness(client):
    viewer = login(client, "viewer")
    assert client.get("/api/v1/state/map", headers=viewer).json()["data_fresh"] is False
    push_state(client)
    body = client.get("/api/v1/state/map", headers=viewer).json()
    assert body["data_fresh"] is True
    assert body["system_mode"] == "auto"


def test_sync_upsert_is_idempotent(client):
    push_state(client)
    push_state(client, tank=42.0)
    body = client.get("/api/v1/state/map", headers=SIM).json()
    assert body["tank_level_pct"] == 42.0
    assert len(body["zones"]) == 12
