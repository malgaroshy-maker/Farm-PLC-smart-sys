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
async def test_briefing_with_real_alarms_in_db(client):
    """Regression test: verify daily briefing succeeds with real Alarm rows in DB (no a.name AttributeError)."""
    from uuid import uuid4

    from app.models.alarm import Alarm

    _set_dummy_weather()
    async with async_session_factory() as db:
        now = clock.farm_now()
        alarm1 = Alarm(
            id=f"alm_{uuid4().hex[:8]}",
            alarm_code="ALM-001",
            severity="S1",
            category="water_source",
            status="active_unacked",
            triggered_at=now,
            message_en="Low tank level",
            message_ar="مستوى الخزان منخفض",
        )
        alarm2 = Alarm(
            id=f"alm_{uuid4().hex[:8]}",
            alarm_code="ALM-012",
            severity="S2",
            category="process",
            status="cleared",
            triggered_at=now,
            message_en="No flow detected",
            message_ar="لا يوجد تدفق",
        )
        db.add_all([alarm1, alarm2])
        await db.commit()

        date_str = now.strftime("%Y-%m-%d")
        briefing = await get_or_generate_daily_briefing(
            db, target_date=date_str, force_refresh=True
        )
        assert briefing is not None
        assert briefing.title is not None
        assert briefing.summary is not None


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


@pytest.mark.asyncio
async def test_farm_context_block_builds_from_db_with_exact_zone_count():
    """Verify build_farm_context_block queries DB and explicitly states the exact zone count (12)."""
    from app.services.ai.agent import build_farm_context_block

    context_str = await build_farm_context_block(async_session_factory)
    assert "12" in context_str
    assert "Farm Facts: The farm has exactly 12 irrigation zones" in context_str
    # Verify zone names & crops from DB are present
    assert "zone_zaytoun" in context_str or "Z1" in context_str or "Zone" in context_str


@pytest.mark.asyncio
async def test_briefing_arabic_et0_and_clean_purity(client):
    """Verify briefing formats ET0 cleanly in Arabic ('التبخر-نتح المرجعي ET₀ = ...') and contains no garbled text."""
    from app.services.ai.rules import rule_service
    from app.services.weather import WeatherData, WeatherDaySummary, WeatherForecast

    now_iso = clock.farm_now().isoformat()
    cur = WeatherData(
        timestamp=now_iso,
        temperature_c=22.0,
        humidity_pct=50.0,
        wind_speed_kmh=10.0,
        precipitation_mm=0.0,
        precipitation_probability_pct=15.0,
        et0_mm=3.28,
    )
    day = WeatherDaySummary(
        date="2026-11-20",
        temp_min_c=18.0,
        temp_max_c=31.5,
        precipitation_probability_pct=15.0,
        precipitation_total_mm=0.0,
        et0_mm=3.28,
    )
    dummy_forecast = WeatherForecast(
        current=cur,
        daily=[day],
        hourly=[cur],
        last_fetched_at=now_iso,
        source="test",
        cached=False,
    )

    briefing = rule_service.daily_briefing(
        date_str="2026-11-20",
        forecast=dummy_forecast,
        cycles=[],
        alarms=[],
    )

    assert "التبخر-نتح المرجعي ET₀ = 3.28 مم" in briefing.weather_summary_ar
    assert "pent reference" not in briefing.weather_summary_ar
    assert "13" not in briefing.summary_ar


def test_rule_briefing_without_forecast_invents_no_weather():
    """No forecast -> say so; never a made-up temperature."""
    from app.services.ai.rules import rule_service

    b = rule_service.daily_briefing(
        "2026-11-23", cycles_summary=[{"water_volume_m3": 2.0, "outcome": "completed"}]
    )
    assert "22.0" not in b.weather_summary
    assert "No weather forecast" in b.weather_summary
    assert "لا تتوفر توقعات" in b.weather_summary_ar


def test_briefing_prompt_has_no_hard_coded_zone_count():
    import inspect

    from app.services.ai import agent

    src = inspect.getsource(agent.run_daily_briefing)
    assert "exactly 12" not in src
