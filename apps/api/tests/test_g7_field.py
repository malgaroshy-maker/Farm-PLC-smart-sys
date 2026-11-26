"""G7 field readiness on the API: panel switches, power, unexpected flow, unattended cycles."""

from datetime import timedelta

import pytest
from conftest import SIM, login, push_state

from app.core.timeutil import utcnow

START = {"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"}
STOP = {"command_type": "stop_zone", "target_type": "zone", "target_id": "zone_enab"}


def alarms(client, headers):
    return client.get("/api/v1/alarms", headers=headers).json()


def codes(client, headers):
    return [
        (a["alarm_code"], a.get("zone_id") or a.get("device_id")) for a in alarms(client, headers)
    ]


def test_gateway_retries_and_older_packets_do_not_roll_back_state(client):
    now = utcnow()
    current = {
        "device_key": "system_mode",
        "updated_at": now.isoformat(),
        "state_json": {"mode": "auto", "power_ok": False},
    }
    old = {
        **current,
        "updated_at": (now - timedelta(seconds=1)).isoformat(),
        "state_json": {"mode": "hand", "power_ok": True},
    }

    def sync(batch):
        result = client.post("/api/v1/state/sync", json=batch, headers=SIM)
        assert result.status_code == 200
        return result.json()["accepted"]

    assert sync([current, old]) == 1
    assert sync([old]) == 0
    assert sync([{**current, "state_json": {"power_ok": False, "mode": "auto"}}]) == 0
    state = client.get("/api/v1/state/map", headers=login(client, "operator")).json()
    assert state["system_mode"] == "auto" and state["power_ok"] is False


def test_panel_switch_shows_on_the_map_and_raises_info_alarm(client):
    op = login(client, "operator")
    push_state(
        client,
        zone_extra={"zone_enab": {"panel_mode": "off"}},
        pump_extra={"pump_well_01": {"panel_mode": "hand"}},
    )
    state = client.get("/api/v1/state/map", headers=op).json()
    z = next(z for z in state["zones"] if z["zone_id"] == "zone_enab")
    p = next(p for p in state["pumps"] if p["pump_id"] == "pump_well_01")
    assert z["panel_mode"] == "off" and p["panel_mode"] == "hand"
    found = codes(client, op)
    assert ("ALM-042", "zone_enab") in found and ("ALM-042", "pump_well_01") in found
    # back to auto clears them
    push_state(client)
    assert not [c for c in codes(client, op) if c[0] == "ALM-042"]


def test_app_cannot_start_or_stop_a_zone_in_manual(client):
    op = login(client, "operator")
    push_state(client, zone_extra={"zone_enab": {"panel_mode": "off"}})
    r = client.post("/api/v1/commands", json=START, headers=op)
    assert r.status_code == 409 and r.json()["code"] == "zone_manual"
    push_state(
        client, zone_states={"zone_enab": "running"}, zone_extra={"zone_enab": {"panel_mode": "on"}}
    )
    r = client.post("/api/v1/commands", json=STOP, headers=op)
    assert r.status_code == 409 and r.json()["code"] == "zone_manual"


def test_no_power_and_pumps_switched_off_block_starts(client):
    op = login(client, "operator")
    push_state(client, system_extra={"power_ok": False})
    assert client.post("/api/v1/commands", json=START, headers=op).json()["code"] == "no_power"
    state = client.get("/api/v1/state/map", headers=op).json()
    assert state["power_ok"] is False
    off = {"panel_mode": "off"}
    push_state(client, pump_extra={"pump_well_01": off, "pump_booster_01": off})
    assert (
        client.post("/api/v1/commands", json=START, headers=op).json()["code"]
        == "no_pump_available"
    )


def test_unexpected_flow_and_stray_valve_raise_alm_021(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "alarm_debounce_sec", 0.0)
    op = login(client, "operator")
    push_state(client, flow=3.0)
    push_state(client, flow=3.0)
    assert any(c == ("ALM-021", None) for c in codes(client, op))
    push_state(
        client, valves=[{"valve_id": "valve_enab", "zone_id": "zone_enab", "status": "open"}]
    )
    push_state(
        client, valves=[{"valve_id": "valve_enab", "zone_id": "zone_enab", "status": "open"}]
    )
    assert any(c[0] == "ALM-021" and c[1] in ("zone_enab", "valve_enab") for c in codes(client, op))


def test_running_zone_alone_is_not_unexpected(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "alarm_debounce_sec", 0.0)
    op = login(client, "operator")
    for _ in range(2):
        push_state(
            client,
            flow=5.0,
            zone_states={"zone_enab": "running"},
            valves=[{"valve_id": "valve_enab", "zone_id": "zone_enab", "status": "open"}],
        )
    assert not [c for c in codes(client, op) if c[0] == "ALM-021"]


def test_panel_run_gets_a_cycle_record(client):
    admin = login(client, "admin")
    push_state(client)
    push_state(
        client,
        zone_states={"zone_enab": "running"},
        zone_extra={"zone_enab": {"panel_mode": "on", "run_source": "panel"}},
    )
    cycles = client.get("/api/v1/cycles", params={"zone_id": "zone_enab"}, headers=admin).json()
    rows = cycles["items"] if isinstance(cycles, dict) else cycles
    assert rows and rows[0]["initiated_by_type"] == "plc" and rows[0]["initiated_by_id"] == "panel"
    push_state(client, zone_states={"zone_enab": "completed"})
    cycles = client.get("/api/v1/cycles", params={"zone_id": "zone_enab"}, headers=admin).json()
    rows = cycles["items"] if isinstance(cycles, dict) else cycles
    assert rows[0]["actual_end_at"] is not None


def test_same_controller_packet_can_recover_an_interrupted_cycle_write(client, monkeypatch):
    from app.routers import state

    push_state(client)
    stamp = utcnow().isoformat()
    payload = [
        {
            "device_key": "zone_zone_enab",
            "updated_at": stamp,
            "state_json": {
                "zone_id": "zone_enab",
                "state": "running",
                "run_source": "panel",
                "health": "healthy",
                "last_updated": stamp,
            },
        }
    ]
    persist = state.record_unattended_cycle_start

    async def fail_after_flush(*args):
        await persist(*args)
        raise RuntimeError("Interrupted cycle write")

    with monkeypatch.context() as patch:
        patch.setattr(state, "record_unattended_cycle_start", fail_after_flush)
        with pytest.raises(RuntimeError, match="Interrupted cycle write"):
            client.post("/api/v1/state/sync", headers=SIM, json=payload)

    retry = client.post("/api/v1/state/sync", headers=SIM, json=payload)
    assert retry.status_code == 200 and retry.json()["accepted"] == 1
    replay = client.post("/api/v1/state/sync", headers=SIM, json=payload)
    assert replay.status_code == 200 and replay.json()["accepted"] == 0
    cycles = client.get(
        "/api/v1/cycles?zone_id=zone_enab", headers=login(client, "operator")
    ).json()
    assert [row["initiated_by_id"] for row in cycles["items"]] == ["panel"]


def test_invalid_device_snapshot_does_not_replace_map_state(client):
    push_state(client)
    response = client.post(
        "/api/v1/state/sync",
        headers=SIM,
        json=[
            {
                "device_key": "zone_zone_enab",
                "updated_at": utcnow().isoformat(),
                "state_json": {"zone_id": "zone_enab", "state": "running"},
            }
        ],
    )
    assert response.status_code == 422
    current = client.get("/api/v1/state/map", headers=login(client, "viewer"))
    assert current.status_code == 200
    assert next(z for z in current.json()["zones"] if z["zone_id"] == "zone_enab")["state"] == "off"


def test_set_panel_command_is_simulation_only_and_admin_only(client):
    admin, op = login(client, "admin"), login(client, "operator")
    push_state(client)
    body = {
        "command_type": "set_panel",
        "target_type": "simulator",
        "target_id": "zone_enab",
        "payload": {"kind": "zone", "position": "on"},
    }
    assert client.post("/api/v1/commands", json=body, headers=op).status_code == 403
    assert client.post("/api/v1/commands", json=body, headers=admin).status_code == 201
    bad = {**body, "payload": {"kind": "zone", "position": "hand"}}
    assert client.post("/api/v1/commands", json=bad, headers=admin).status_code == 422
    assert SIM


def test_clogged_filter_raises_maintenance_alarm(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "alarm_debounce_sec", 0.0)
    op = login(client, "operator")
    push_state(client)
    client.post(
        "/api/v1/state/sync",
        headers=SIM,
        json=[
            {
                "device_key": "simulation_stats",
                "updated_at": "2030-01-01T00:00:00+00:00",
                "state_json": {
                    "tank_level_pct": 80,
                    "main_pressure_bar": 0,
                    "main_flow_m3h": 0,
                    "filter_dp_bar": 0.7,
                    "well_level_m": 9.0,
                },
            },
        ],
    )
    state = client.get("/api/v1/state/map", headers=op).json()
    assert state["filter_dp_bar"] == 0.7 and state["well_level_m"] == 9.0
    assert any(c[0] == "ALM-039" for c in codes(client, op))
