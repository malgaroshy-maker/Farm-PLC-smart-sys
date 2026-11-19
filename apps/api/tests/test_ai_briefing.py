"""Tests for Daily AI Briefing Service on Virtual Farm Clock (Milestone E)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai import models
from sqlalchemy import select

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.ai import AIBriefing, AIInsight
from app.services.ai.briefing import check_scheduled_briefing, get_or_generate_daily_briefing
from app.services.weather import WeatherData, WeatherDaySummary, WeatherForecast, weather_service

models.ALLOW_MODEL_REQUESTS = False


def _set_dummy_weather():
    now_iso = clock.farm_now().isoformat()
    cur = WeatherData(
        timestamp=now_iso,
        temperature_c=26.0,
        humidity_pct=45.0,
        wind_speed_kmh=12.0,
        precipitation_mm=0.0,
        precipitation_probability_pct=0.0,
        et0_mm=4.8,
    )
    day = WeatherDaySummary(
        date=clock.farm_now().strftime("%Y-%m-%d"),
        temp_min_c=17.0,
        temp_max_c=29.0,
        precipitation_total_mm=0.0,
        precipitation_probability_pct=0.0,
        et0_mm=4.8,
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


@pytest.mark.asyncio
async def test_get_or_generate_daily_briefing(client):
    """Verify daily briefing generation, DB persistence, and cache hit."""
    _set_dummy_weather()

    async with async_session_factory() as db:
        date_str = "2026-11-20"
        briefing = await get_or_generate_daily_briefing(
            db, target_date=date_str, force_refresh=True
        )

        assert briefing is not None
        assert briefing.date == date_str
        assert briefing.title is not None
        assert briefing.summary is not None
        assert briefing.weather_summary is not None
        assert briefing.irrigation_overview is not None

        # Verify saved in ai_briefings table
        row = await db.get(AIBriefing, briefing.id)
        assert row is not None
        assert row.date == date_str

        # Verify saved in ai_insights table for UI contract compatibility
        res = await db.execute(select(AIInsight).where(AIInsight.date == date_str))
        insight = res.scalar_one_or_none()
        assert insight is not None
        assert insight.insight_type == "daily_summary"

        # Subsequent call without force_refresh hits DB cache
        cached = await get_or_generate_daily_briefing(db, target_date=date_str, force_refresh=False)
        assert cached.id == briefing.id


@pytest.mark.asyncio
async def test_scheduled_briefing_on_farm_time(client):
    """Briefing generated when farm clock reaches 06:00, skipped before 06:00, and runs only once."""
    _set_dummy_weather()
    tz = ZoneInfo(settings.farm_timezone)

    original_now = clock.farm_now

    try:
        # Case 1: Before 06:00 farm time (e.g. 05:45) -> No briefing generated
        t_0545 = datetime(2026, 11, 21, 5, 45, tzinfo=tz)
        clock.farm_now = lambda: t_0545

        async with async_session_factory() as db:
            b1 = await check_scheduled_briefing(db)
            assert b1 is None

        # Case 2: At or after 06:00 farm time (e.g. 06:05) -> Briefing generated
        t_0605 = datetime(2026, 11, 21, 6, 5, tzinfo=tz)
        clock.farm_now = lambda: t_0605

        async with async_session_factory() as db:
            b2 = await check_scheduled_briefing(db)
            assert b2 is not None
            assert b2.date == "2026-11-21"

        # Case 3: Calling again on same farm day (e.g. 06:30) -> Skipped because already generated
        t_0630 = datetime(2026, 11, 21, 6, 30, tzinfo=tz)
        clock.farm_now = lambda: t_0630

        async with async_session_factory() as db:
            b3 = await check_scheduled_briefing(db)
            assert b3 is None
    finally:
        clock.farm_now = original_now
