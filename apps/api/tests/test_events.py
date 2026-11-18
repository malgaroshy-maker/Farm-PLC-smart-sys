from conftest import login, push_state


def test_event_log_records_logins_and_commands(client):
    push_state(client)
    op = login(client, "operator")
    client.post(
        "/api/v1/commands",
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
        headers=op,
    )
    events = client.get("/api/v1/events", headers=login(client, "viewer")).json()
    types = [e["event_type"] for e in events]
    assert "command.requested" in types and "user.login" in types
    cmd = next(e for e in events if e["event_type"] == "command.requested")
    assert cmd["actor_name"] == "Operator" and cmd["entity_id"] == "zone_enab"
    assert events == sorted(events, key=lambda e: -e["id"])  # newest first


def test_event_log_filters_and_paginates(client):
    for _ in range(3):
        login(client, "viewer")
    viewer = login(client, "viewer")
    only_logins = client.get("/api/v1/events?category=user", headers=viewer).json()
    assert only_logins and {e["event_type"] for e in only_logins} == {"user.login"}
    page1 = client.get("/api/v1/events?limit=2", headers=viewer).json()
    page2 = client.get(f"/api/v1/events?limit=2&before_id={page1[-1]['id']}", headers=viewer).json()
    assert page2 and page2[0]["id"] < page1[-1]["id"]


def test_event_log_requires_auth(client):
    assert client.get("/api/v1/events").status_code == 401
