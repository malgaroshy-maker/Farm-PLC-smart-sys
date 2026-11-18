from conftest import SIM, login


def test_login_success_returns_token_and_user(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["role"] == "owner_admin"
    assert "password_hash" not in body["user"]


def test_login_wrong_password_rejected(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_returns_current_user(client):
    r = client.get("/api/v1/auth/me", headers=login(client, "operator"))
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_read_endpoints_require_auth(client):
    for path in ("/api/v1/zones", "/api/v1/farm", "/api/v1/state/map", "/api/v1/pumps"):
        assert client.get(path).status_code == 401, path


def test_garbage_token_rejected(client):
    r = client.get("/api/v1/zones", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_viewer_can_read(client):
    r = client.get("/api/v1/zones", headers=login(client, "viewer"))
    assert r.status_code == 200
    assert len(r.json()) == 12


def test_only_admin_can_edit_zone(client):
    body = {"default_duration_min": 30}
    assert (
        client.patch(
            "/api/v1/zones/zone_enab", json=body, headers=login(client, "operator")
        ).status_code
        == 403
    )
    r = client.patch("/api/v1/zones/zone_enab", json=body, headers=login(client, "admin"))
    assert r.status_code == 200
    assert r.json()["default_duration_min"] == 30


def test_state_sync_requires_service_token(client):
    assert client.post("/api/v1/state/sync", json=[]).status_code == 401
    user = login(client, "admin")
    assert client.post("/api/v1/state/sync", json=[], headers=user).status_code == 403
    assert client.post("/api/v1/state/sync", json=[], headers=SIM).status_code == 200


def test_service_token_cannot_issue_user_commands(client):
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "stop_all", "target_type": "system"},
        headers=SIM,
    )
    assert r.status_code == 403


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ai"] == "not_implemented"
