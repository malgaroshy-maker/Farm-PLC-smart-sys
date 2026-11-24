"""Tests for schedule/program endpoints (/api/v1/schedules)."""

from conftest import login


def test_list_and_create_program(client):
    admin = login(client, "admin")
    # Create program
    resp = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Morning Grove",
            "enabled": True,
            "start_time_local": "06:00",
            "weekday_mask": "1,2,3,4,5",
            "steps": [
                {"zone_id": "zone_enab", "step_order": 1, "duration_min": 25},
                {"zone_id": "zone_fruit_mix", "step_order": 2, "duration_min": 20},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Morning Grove"
    assert len(data["steps"]) == 2
    assert data["total_duration_min"] == 45
    prog_id = data["id"]

    # List programs
    list_resp = client.get("/api/v1/schedules", headers=admin)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(p["id"] == prog_id for p in items)


def test_schedule_rbac(client):
    viewer = login(client, "viewer")
    operator = login(client, "operator")

    # Viewer cannot create schedule
    resp_viewer = client.post(
        "/api/v1/schedules",
        headers=viewer,
        json={
            "name": "Unauthorized",
            "start_time_local": "08:00",
            "steps": [{"zone_id": "zone_grapes_1", "step_order": 1, "duration_min": 15}],
        },
    )
    assert resp_viewer.status_code == 403

    # Operator cannot create schedule (Admin only per owner decision)
    resp_op = client.post(
        "/api/v1/schedules",
        headers=operator,
        json={
            "name": "Operator Create",
            "start_time_local": "08:00",
            "steps": [{"zone_id": "zone_grapes_1", "step_order": 1, "duration_min": 15}],
        },
    )
    assert resp_op.status_code == 403


def test_schedule_operator_toggle(client):
    admin = login(client, "admin")
    operator = login(client, "operator")

    # Create by admin
    resp = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Toggle Test",
            "start_time_local": "14:00",
            "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 20}],
        },
    )
    assert resp.status_code == 201, resp.text
    prog_id = resp.json()["id"]

    # Operator toggles disabled
    tog_resp = client.patch(
        f"/api/v1/schedules/{prog_id}/toggle",
        headers=operator,
        json={"enabled": False},
    )
    assert tog_resp.status_code == 200
    assert tog_resp.json()["enabled"] is False

    # Operator toggles enabled
    tog_resp2 = client.patch(
        f"/api/v1/schedules/{prog_id}/toggle",
        headers=operator,
        json={"enabled": True},
    )
    assert tog_resp2.status_code == 200
    assert tog_resp2.json()["enabled"] is True


def test_schedule_conflict_rejected(client):
    admin = login(client, "admin")

    # Create Program A: 10:00 - 10:40 on Monday (duration 40 min <= max 45 min)
    res1 = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Program A",
            "start_time_local": "10:00",
            "weekday_mask": "1",
            "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 40}],
        },
    )
    assert res1.status_code == 201, res1.text

    # Attempt to create Program B overlapping: 10:20 on Monday -> should 409
    res2 = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Program B",
            "start_time_local": "10:20",
            "weekday_mask": "1",
            "steps": [{"zone_id": "zone_fruit_mix", "step_order": 1, "duration_min": 30}],
        },
    )
    assert res2.status_code == 409
    data = res2.json()
    assert "conflicts" in data["detail"]
    assert any(c["code"] == "SCHEDULE_OVERLAP" for c in data["detail"]["conflicts"])


def test_upcoming_runs(client):
    admin = login(client, "admin")
    resp = client.get(
        "/api/v1/schedules/upcoming?hours=48",
        headers=admin,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)


def test_live_conflict_check(client):
    """The program editor checks conflicts while typing; nothing is saved (G6)."""
    admin = login(client, "admin")
    a = {
        "name": "Program A",
        "start_time_local": "10:00",
        "weekday_mask": "1",
        "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 40}],
    }
    created = client.post("/api/v1/schedules", headers=admin, json=a)
    assert created.status_code == 201, created.text
    before = len(client.get("/api/v1/schedules", headers=admin).json())

    clash = {
        **a,
        "name": "Program B",
        "start_time_local": "10:20",
        "steps": [{"zone_id": "zone_fruit_mix", "step_order": 1, "duration_min": 30}],
    }
    res = client.post("/api/v1/schedules/check-conflicts", headers=admin, json={"program": clash})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["conflict"]["code"] == "SCHEDULE_OVERLAP"
    assert body["conflict"]["message_ar"]

    # editing A itself must not clash with A
    own = client.post(
        "/api/v1/schedules/check-conflicts",
        headers=admin,
        json={"program": a, "exclude_program_id": created.json()["id"]},
    )
    assert own.json() == {"ok": True, "conflict": None, "conflicts": []}
    assert len(client.get("/api/v1/schedules", headers=admin).json()) == before

    viewer = login(client, "viewer")
    assert (
        client.post(
            "/api/v1/schedules/check-conflicts", headers=viewer, json={"program": a}
        ).status_code
        == 403
    )

    # leave no enabled program behind for the scheduler tests
    assert (
        client.delete(f"/api/v1/schedules/{created.json()['id']}", headers=admin).status_code == 204
    )
