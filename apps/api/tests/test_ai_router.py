"""Tests for AI Router Endpoints (/api/v1/ai and /health) (Milestone E)."""

from datetime import UTC, datetime

from conftest import login
from pydantic_ai import models

from app.core.clock import clock
from app.services.weather import WeatherData, WeatherDaySummary, WeatherForecast, weather_service

models.ALLOW_MODEL_REQUESTS = False


def _set_dummy_weather():
    now_iso = clock.farm_now().isoformat()
    cur = WeatherData(
        timestamp=now_iso,
        temperature_c=27.0,
        humidity_pct=40.0,
        wind_speed_kmh=14.0,
        precipitation_mm=0.0,
        precipitation_probability_pct=0.0,
        et0_mm=5.0,
    )
    day = WeatherDaySummary(
        date=clock.farm_now().strftime("%Y-%m-%d"),
        temp_min_c=18.0,
        temp_max_c=30.0,
        precipitation_total_mm=0.0,
        precipitation_probability_pct=0.0,
        et0_mm=5.0,
    )
    weather_service._cached_forecast = WeatherForecast(
        current=cur,
        hourly=[cur],
        daily=[day],
        last_fetched_at=now_iso,
        source="test",
        cached=False,
    )
    weather_service._cache_time = clock.farm_now()


def test_health_endpoint_ai_and_weather(client):
    """GET /health reports ai and weather service status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "ai" in data
    assert data["ai"]["status"] == "ready"
    assert data["ai"]["primary_provider"] == "apinex"
    assert data["ai"]["fallback_provider"] == "gemini"
    assert "weather" in data
    assert data["weather"]["provider"] == "open-meteo"


def test_explain_alarm_endpoints(client):
    """POST /api/v1/ai/explain-alarm and /alarm-assistant return structured explanation."""
    admin = login(client, "admin")

    # Call with alarm_code
    r1 = client.post(
        "/api/v1/ai/explain-alarm",
        headers=admin,
        json={"alarm_code": "ALM-004", "language": "ar"},
    )
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    assert data1["alarm_code"] == "ALM-004"
    assert "title" in data1
    assert "diagnosis" in data1
    assert len(data1["suggested_actions"]) > 0

    # Call /alarm-assistant (contract compatibility)
    r2 = client.post(
        "/api/v1/ai/alarm-assistant",
        headers=admin,
        json={"alarm_code": "ALM-006", "language": "en"},
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["alarm_code"] == "ALM-006"


def test_ai_chat_endpoint(client):
    """POST /api/v1/ai/chat returns assistant answer."""
    operator = login(client, "operator")
    resp = client.post(
        "/api/v1/ai/chat",
        headers=operator,
        json={"message": "ما هي حالة الطقس اليوم؟", "language": "ar"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "reply" in data
    assert "reply_ar" in data
    assert data["provider_used"] is not None


def test_suggestions_lifecycle_endpoints(client):
    """Test listing, evaluating, approving, and rejecting suggestions."""
    _set_dummy_weather()
    # Modify dummy weather to trigger rain threshold
    weather_service._cached_forecast.daily[0].precipitation_total_mm = 6.0
    weather_service._cached_forecast.daily[0].precipitation_probability_pct = 80.0

    admin = login(client, "admin")

    schedule = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Advisor fixture",
            "start_time_local": "06:00",
            "steps": [{"zone_id": "zone_rumman_1", "step_order": 1, "duration_min": 15}],
        },
    )
    assert schedule.status_code in (200, 201), schedule.text
    # 1. Trigger evaluation
    eval_resp = client.post("/api/v1/ai/suggestions/evaluate", headers=admin)
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()
    sug_id = eval_data.get("id")
    assert sug_id is not None
    assert eval_data.get("status") == "pending"

    before_approval = client.get("/api/v1/ai/briefing", headers=admin)
    assert before_approval.status_code == 200
    planned = before_approval.json()
    assert [item["program_name"] for item in planned["schedules_today"]] == ["Advisor fixture"]

    # 2. List suggestions
    list_resp = client.get("/api/v1/ai/suggestions?status=pending", headers=admin)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == sug_id for item in items)

    # 3. Approve suggestion
    app_resp = client.post(f"/api/v1/ai/suggestions/{sug_id}/approve", headers=admin)
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "approved"
    assert "override_id" in app_data

    after_approval = client.get("/api/v1/ai/briefing", headers=admin)
    assert after_approval.status_code == 200
    assert after_approval.json()["id"] == planned["id"]
    assert after_approval.json()["schedules_today"] == []

    # 4. Rejecting already approved suggestion returns 400
    rej_fail = client.post(f"/api/v1/ai/suggestions/{sug_id}/reject", headers=admin)
    assert rej_fail.status_code == 400


def test_daily_briefing_endpoints(client):
    """GET /api/v1/ai/briefing and /insights/daily return structured daily briefing."""
    _set_dummy_weather()
    operator = login(client, "operator")

    r1 = client.get("/api/v1/ai/briefing?date=2026-11-20", headers=operator)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["date"] == "2026-11-20"
    assert "title" in d1
    assert "summary" in d1
    assert "weather_summary" in d1
    assert "irrigation_overview" in d1
    assert d1["schedules_today"] is None

    # Contract alias /insights/daily
    r2 = client.get("/api/v1/ai/insights/daily?date=2026-11-20", headers=operator)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["id"] == d1["id"]


def test_briefing_schedule_uses_the_farm_calendar_day(client, monkeypatch):
    # Thursday 00:35 in Tripoli still falls on Wednesday in UTC.
    monkeypatch.setattr(clock, "farm_now", lambda: datetime(2030, 11, 27, 22, 35, tzinfo=UTC))
    _set_dummy_weather()
    admin = login(client, "admin")
    for name, weekday, enabled, start in (
        ("Tonight", "4", True, "18:00"),
        ("Early", "4", True, "00:10"),
        ("Wednesday only", "3", True, "12:00"),
        ("Disabled", "4", False, "10:00"),
    ):
        result = client.post(
            "/api/v1/schedules",
            headers=admin,
            json={
                "name": name,
                "enabled": enabled,
                "start_time_local": start,
                "weekday_mask": weekday,
                "steps": [{"zone_id": "zone_rumman_1", "step_order": 1, "duration_min": 10}],
            },
        )
        assert result.status_code == 201, result.text

    response = client.get("/api/v1/ai/briefing", headers=admin)
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2030-11-28"
    assert [(item["program_name"], item["start_time"]) for item in data["schedules_today"]] == [
        ("Early", "00:10"),
        ("Tonight", "18:00"),
    ]
    assert client.get("/api/v1/ai/briefing?date=invalid", headers=admin).status_code == 422


def test_weather_and_settings_endpoints(client):
    """GET /api/v1/ai/weather/forecast, /current, /settings, /models."""
    _set_dummy_weather()
    operator = login(client, "operator")

    # Forecast
    r_fc = client.get("/api/v1/ai/weather/forecast", headers=operator)
    assert r_fc.status_code == 200
    assert "current" in r_fc.json()

    # Current
    r_cur = client.get("/api/v1/ai/weather/current", headers=operator)
    assert r_cur.status_code == 200
    assert r_cur.json()["temperature_c"] == 27.0

    # Settings
    r_set = client.get("/api/v1/ai/settings", headers=operator)
    assert r_set.status_code == 200
    s_data = r_set.json()
    assert s_data["primary_provider"] == "apinex"
    assert s_data["weather_coordinates"]["latitude"] == 32.516250

    # Models
    r_mod = client.get("/api/v1/ai/models", headers=operator)
    assert r_mod.status_code == 200
    m_data = r_mod.json()
    assert "models" in m_data
    assert "selected" in m_data


def test_ai_settings_put_and_model_switching(client):
    """PUT /api/v1/ai/settings is admin-only and updates persistent AI configuration."""
    admin = login(client, "admin")
    operator = login(client, "operator")

    # Operator is forbidden to update settings
    r_forbidden = client.put(
        "/api/v1/ai/settings",
        headers=operator,
        json={"model_alarm": "free/glm-5.3-flash"},
    )
    assert r_forbidden.status_code == 403

    # Admin updates model per feature and global settings
    r_put = client.put(
        "/api/v1/ai/settings",
        headers=admin,
        json={
            "model_alarm": "free/glm-5.3-flash",
            "model_chat": "free/gemini-3.8-flash",
            "timeout_sec": 40.0,
            "global_enabled": True,
        },
    )
    assert r_put.status_code == 200, r_put.text
    put_data = r_put.json()
    assert put_data["model_alarm"] == "free/glm-5.3-flash"
    assert put_data["model_chat"] == "free/gemini-3.8-flash"
    assert put_data["timeout_sec"] == 40.0
    assert put_data["global_enabled"] is True

    # GET returns updated configuration
    r_get = client.get("/api/v1/ai/settings", headers=operator)
    assert r_get.status_code == 200
    get_data = r_get.json()
    assert get_data["model_alarm"] == "free/glm-5.3-flash"
    assert "recent_calls" in get_data
    assert "key_status" in get_data


def test_global_ai_toggle_offline_fallback(client):
    """When global AI is disabled via settings, all requests gracefully fallback to rule-based."""
    admin = login(client, "admin")

    # Disable AI globally
    client.put("/api/v1/ai/settings", headers=admin, json={"global_enabled": False})

    # Call /explain-alarm -> should succeed with rule_based provider
    resp = client.post(
        "/api/v1/ai/explain-alarm",
        headers=admin,
        json={"alarm_code": "ALM-004", "language": "ar"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_used"] == "rule_based"

    # Re-enable AI
    client.put("/api/v1/ai/settings", headers=admin, json={"global_enabled": True})


def test_ai_rate_limiting(client):
    """Per-user sliding window rate limiting blocks spamming after threshold."""
    operator = login(client, "operator")
    from app.routers.ai import AI_RATE_LIMIT_MAX, reset_ai_rate_limits

    reset_ai_rate_limits()

    # Issue requests up to the limit
    for _ in range(AI_RATE_LIMIT_MAX):
        r = client.post(
            "/api/v1/ai/explain-alarm",
            headers=operator,
            json={"alarm_code": "ALM-004"},
        )
        assert r.status_code == 200

    # Next request must be rate limited (429)
    r_exceeded = client.post(
        "/api/v1/ai/explain-alarm",
        headers=operator,
        json={"alarm_code": "ALM-004"},
    )
    assert r_exceeded.status_code == 429
    assert "Rate limit exceeded" in r_exceeded.json()["detail"]

    reset_ai_rate_limits()


def test_health_degraded_when_primary_fails(client):
    """Health check reports ai: degraded when recent calls fall back due to primary failure."""
    from app.services.ai.agent import record_ai_call, reset_call_history

    reset_call_history()

    # Normal health check -> ready
    r1 = client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["ai"]["status"] == "ready"

    # Record primary failure fallback
    record_ai_call(
        feature="explain_alarm",
        provider="rule_based",
        model="offline_rules",
        latency_ms=120.0,
        fallback_reason="APInex 503 Service Unavailable",
    )

    # Health check -> degraded
    r2 = client.get("/health")
    assert r2.status_code == 200
    assert r2.json()["ai"]["status"] == "degraded"

    reset_call_history()
