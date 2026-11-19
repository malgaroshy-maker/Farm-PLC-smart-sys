"""Tests for AI Router Endpoints (/api/v1/ai and /health) (Milestone E)."""

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

    # 1. Trigger evaluation
    eval_resp = client.post("/api/v1/ai/suggestions/evaluate", headers=admin)
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()
    sug_id = eval_data.get("id")
    assert sug_id is not None
    assert eval_data.get("status") == "pending"

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

    # Contract alias /insights/daily
    r2 = client.get("/api/v1/ai/insights/daily?date=2026-11-20", headers=operator)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["id"] == d1["id"]


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
