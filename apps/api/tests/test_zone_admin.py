"""Milestone G3: zones & equipment admin — edit with validation, add, disable (never delete)."""

from conftest import login


def test_edit_zone_validates_and_broadcasts(client):
    h = login(client, "admin")
    r = client.patch("/api/v1/zones/zone_enab", json={"name": "Grapes", "area_ha": 0.12}, headers=h)
    assert r.status_code == 200 and r.json()["area_ha"] == 0.12
    bad = client.patch(
        "/api/v1/zones/zone_enab", json={"flow_min_m3h": 50, "flow_max_m3h": 5}, headers=h
    )
    assert bad.status_code == 422
    assert (
        client.patch("/api/v1/zones/zone_enab", json={"crop_type": "palms"}, headers=h).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/zones/zone_enab", json={"name": "x"}, headers=login(client, "operator")
        ).status_code
        == 403
    )


def test_add_zone_creates_valve_and_sensor(client):
    h = login(client, "admin")
    body = {
        "code": "LEMON_1",
        "name": "Lemon 1",
        "name_ar": "ليمون 1",
        "crop_type": "other",
        "area_ha": 0.3,
    }
    r = client.post("/api/v1/zones", json=body, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "zone_lemon_1" and r.json()["enabled"] is True
    valves = client.get("/api/v1/valves", headers=h).json()
    assert any(v["id"] == "valve_lemon_1" and v["zone_id"] == "zone_lemon_1" for v in valves)
    sensors = client.get("/api/v1/sensors", headers=h).json()
    assert any(s["id"] == "sensor_moisture_lemon_1" for s in sensors)
    assert client.post("/api/v1/zones", json=body, headers=h).status_code == 409
    assert (
        client.post("/api/v1/zones", json={**body, "code": "bad code"}, headers=h).status_code
        == 422
    )


def test_disable_zone_disables_its_valve(client):
    h = login(client, "admin")
    try:
        assert (
            client.patch("/api/v1/zones/zone_rumman_3", json={"enabled": False}, headers=h).json()[
                "enabled"
            ]
            is False
        )
        v = next(
            v
            for v in client.get("/api/v1/valves", headers=h).json()
            if v["zone_id"] == "zone_rumman_3"
        )
        assert v["enabled"] is False
    finally:
        client.patch("/api/v1/zones/zone_rumman_3", json={"enabled": True}, headers=h)
