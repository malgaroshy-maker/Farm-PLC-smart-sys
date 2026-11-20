"""Tests for Open-Meteo Weather Service (Milestone E)."""

import pytest
import respx

from app.config import settings
from app.services.weather import weather_service

MOCK_METEO_PAYLOAD = {
    "current": {
        "time": "2026-11-19T12:00:00Z",
        "temperature_2m": 29.5,
        "relative_humidity_2m": 38.0,
        "precipitation": 0.0,
        "wind_speed_10m": 16.5,
        "wind_direction_10m": 120,
        "weather_code": 0,
        "cloud_cover": 42.0,
    },
    "daily": {
        "time": ["2026-11-19", "2026-11-20"],
        "temperature_2m_max": [33.0, 31.5],
        "temperature_2m_min": [19.0, 18.0],
        "precipitation_sum": [0.0, 0.5],
        "precipitation_probability_max": [10, 25],
        "et0_fao_evapotranspiration": [5.6, 5.1],
        "weather_code": [0, 2],
    },
    "hourly": {
        "time": ["2026-11-19T12:00:00Z", "2026-11-19T13:00:00Z"],
        "temperature_2m": [29.5, 30.2],
        "relative_humidity_2m": [38.0, 36.0],
        "precipitation": [0.0, 0.0],
        "precipitation_probability": [10, 10],
        "wind_speed_10m": [16.5, 17.0],
        "cloud_cover": [40.0, 55.0],
        "et0_fao_evapotranspiration": [0.6, 0.7],
        "weather_code": [0, 0],
    },
}


@pytest.mark.asyncio
async def test_weather_fetch_success():
    """Verify live fetch, WMO parsing, and ET0 extraction."""
    weather_service.reset_cache()

    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        route = respx_mock.get("/v1/forecast").respond(200, json=MOCK_METEO_PAYLOAD)

        forecast = await weather_service.get_forecast()
        assert route.called
        assert forecast.cached is False
        assert forecast.current.temperature_c == 29.5
        assert forecast.current.cloud_cover_pct == 42.0
        assert forecast.current.condition == "clear"
        assert forecast.current.description == "Clear sky"
        assert forecast.current.description_ar == "سماء صافية"
        assert len(forecast.hourly) == 2
        assert forecast.hourly[0].cloud_cover_pct == 40.0
        assert forecast.hourly[1].cloud_cover_pct == 55.0
        assert len(forecast.daily) == 2
        assert forecast.daily[0].et0_mm == 5.6
        assert forecast.daily[0].temp_max_c == 33.0


@pytest.mark.asyncio
async def test_weather_3h_caching():
    """Verify second call within 3h cache TTL uses in-memory cache."""
    weather_service.reset_cache()

    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        route = respx_mock.get("/v1/forecast").respond(200, json=MOCK_METEO_PAYLOAD)

        # First call fetches from API
        fc1 = await weather_service.get_forecast()
        assert route.call_count == 1
        assert fc1.cached is False

        # Second call hits cache
        fc2 = await weather_service.get_forecast()
        assert route.call_count == 1
        assert fc2.cached is True
        assert fc2.current.temperature_c == 29.5

        # Force refresh bypasses cache
        fc3 = await weather_service.get_forecast(force_refresh=True)
        assert route.call_count == 2
        assert fc3.cached is False


@pytest.mark.asyncio
async def test_weather_api_failure_fallback():
    """Verify resilient fallback to stale cache or synthetic fallback when API fails."""
    weather_service.reset_cache()

    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        # 1. First fetch succeeds
        respx_mock.get("/v1/forecast").respond(200, json=MOCK_METEO_PAYLOAD)
        fc1 = await weather_service.get_forecast()
        assert fc1.current.temperature_c == 29.5

        # 2. Subsequent call encounters 500 error on force_refresh
        respx_mock.reset()
        respx_mock.get("/v1/forecast").respond(500)

        fc_fallback = await weather_service.get_forecast(force_refresh=True)
        assert fc_fallback is not None
        assert fc_fallback.cached is True
        assert fc_fallback.current.temperature_c == 29.5

    # 3. Test cold start failure returns default synthetic fallback
    weather_service.reset_cache()
    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        respx_mock.get("/v1/forecast").respond(503)
        fc_cold = await weather_service.get_forecast()
        assert fc_cold is not None
        assert fc_cold.source == "offline_fallback"
        assert fc_cold.current.condition == "clear"


def test_weather_health_reporting():
    """Verify health report metadata."""
    weather_service.reset_cache()
    h = weather_service.health()
    assert h["provider"] == "open-meteo"
    assert h["latitude"] == settings.weather_latitude
    assert h["longitude"] == settings.weather_longitude
    assert h["timezone"] == settings.weather_timezone


@pytest.mark.asyncio
async def test_weather_cloud_cover_persistence_and_fallback(client):
    """Verify cloud_cover_pct is stored in WeatherCache in DB and fallback defaults to 0.0."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.ai import WeatherCache

    weather_service.reset_cache()

    # 1. Fetch with db session persists cloud_cover_pct to WeatherCache
    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        respx_mock.get("/v1/forecast").respond(200, json=MOCK_METEO_PAYLOAD)
        async with async_session_factory() as session:
            forecast = await weather_service.get_forecast(db=session)
            assert forecast.current.cloud_cover_pct == 42.0

            # Verify persisted column in WeatherCache
            row = (
                await session.execute(
                    select(WeatherCache).order_by(WeatherCache.fetched_at.desc()).limit(1)
                )
            ).scalar_one()
            assert row.cloud_cover_pct == 42.0

    # 2. Offline fallback has honest default 0.0
    weather_service.reset_cache()
    with respx.mock(base_url="https://api.open-meteo.com") as respx_mock:
        respx_mock.get("/v1/forecast").respond(500)
        fallback = await weather_service.get_forecast()
        assert fallback.source == "offline_fallback"
        assert fallback.current.cloud_cover_pct == 0.0
