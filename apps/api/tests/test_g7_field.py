"""G7 field readiness on the API: panel switches, power, unexpected flow, unattended cycles."""

from conftest import SIM, login, push_state

START = {"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"}
STOP = {"command_type": "stop_zone", "target_type": "zone", "target_id": "zone_enab"}


def alarms(client, headers):
    return client.get("/api/v1/alarms", headers=headers).json()


def codes(client, headers):
    return [
        (a["alarm_code"], a.get("zone_id") or a.get("device_id")) for a in alarms(client, headers)
    ]


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
