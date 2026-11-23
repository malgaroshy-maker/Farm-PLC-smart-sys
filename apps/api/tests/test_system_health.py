"""Milestone G1: /system/health — one call that says what works and what doesn't."""

from conftest import login, push_state


def test_health_lists_all_checks_for_any_user(client):
    push_state(client)
    body = client.get("/api/v1/system/health", headers=login(client, "viewer")).json()
    keys = [c["key"] for c in body["checks"]]
    assert keys == ["database", "controller", "scheduler", "ai", "weather", "disk"]
    assert body["status"] in {"ok", "warn", "fail"}
    for c in body["checks"]:
        assert c["status"] in {"ok", "warn", "fail"} and c["code"]
    db = next(c for c in body["checks"] if c["key"] == "database")
    assert db["status"] in {"ok", "warn"} and db["detail"]["journal"].lower() == "wal"


def test_controller_link_ok_after_sync(client):
    push_state(client)
    body = client.get("/api/v1/system/health", headers=login(client, "viewer")).json()
    link = next(c for c in body["checks"] if c["key"] == "controller")
    assert link["status"] == "ok" and link["code"] == "link_ok"


def test_paths_only_for_admin(client):
    viewer = client.get("/api/v1/system/health", headers=login(client, "viewer")).json()
    disk_v = next(c for c in viewer["checks"] if c["key"] == "disk")
    assert "db_path" not in disk_v["detail"]
    admin = client.get("/api/v1/system/health", headers=login(client, "admin")).json()
    disk_a = next(c for c in admin["checks"] if c["key"] == "disk")
    assert "free_gb" in disk_a["detail"]


def test_health_needs_login(client):
    assert client.get("/api/v1/system/health").status_code == 401
