"""Milestone G3: feature switches — admin toggles, everyone reads, features obey."""

from conftest import login

from app.services.features import clear_cache


def _set(client, key, on):
    return client.put(
        f"/api/v1/system/features/{key}", json={"enabled": on}, headers=login(client, "admin")
    )


def test_defaults_and_groups_visible_to_any_user(client):
    clear_cache()
    body = client.get("/api/v1/system/features", headers=login(client, "viewer")).json()
    assert body["features"]["ai.chat"] is True
    assert body["features"]["notify.telegram"] is False  # off until configured
    assert body["groups"]["map.farm_life"] == "map"


def test_only_admin_can_switch_and_unknown_keys_rejected(client):
    assert (
        client.put(
            "/api/v1/system/features/ai.chat",
            json={"enabled": False},
            headers=login(client, "operator"),
        ).status_code
        == 403
    )
    assert _set(client, "nope.thing", False).status_code == 404


def test_switched_off_ai_chat_returns_feature_disabled(client):
    try:
        assert _set(client, "ai.chat", False).json()["features"]["ai.chat"] is False
        r = client.post(
            "/api/v1/ai/chat",
            json={"message": "hi", "lang": "ar"},
            headers=login(client, "operator"),
        )
        assert r.status_code == 403 and "feature_disabled:ai.chat" in r.text
    finally:
        _set(client, "ai.chat", True)
        clear_cache()
