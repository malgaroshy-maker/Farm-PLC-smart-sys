"""Tests for Weather Advisor & One-Day Scheduler Override (Milestone E)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai import models
from sqlalchemy import select

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.ai import AISuggestion, ProgramOverride
from app.models.program import Program, ProgramStep
from app.services.ai.advisor import (
    approve_suggestion,
    evaluate_weather_advisor,
    reject_suggestion,
)
from app.services.scheduler import scheduler
from app.services.weather import WeatherData, WeatherDaySummary, WeatherForecast, weather_service

models.ALLOW_MODEL_REQUESTS = False


def _build_forecast_day(
    temp_max: float, precip_mm: float, precip_prob: float, et0: float, date_str: str | None = None
) -> WeatherForecast:
    now_iso = clock.farm_now().isoformat()
    today_date = date_str or clock.farm_now().strftime("%Y-%m-%d")
    cur = WeatherData(
        timestamp=now_iso,
        temperature_c=temp_max - 5.0,
        humidity_pct=40.0,
        wind_speed_kmh=15.0,
        precipitation_mm=precip_mm,
        precipitation_probability_pct=precip_prob,
        et0_mm=et0,
    )
    day = WeatherDaySummary(
        date=today_date,
        temp_min_c=18.0,
        temp_max_c=temp_max,
        precipitation_total_mm=precip_mm,
        precipitation_probability_pct=precip_prob,
        et0_mm=et0,
    )
    return WeatherForecast(
        current=cur,
        hourly=[cur],
        daily=[day],
        last_fetched_at=now_iso,
        source="test",
        cached=False,
    )


@pytest.mark.asyncio
async def test_weather_advisor_rain_threshold(client):
    """Rain > 50% or precip > 2mm triggers skip recommendation."""
    async with async_session_factory() as db:
        weather_service._cached_forecast = _build_forecast_day(
            temp_max=24.0,
            precip_mm=4.5,
            precip_prob=65.0,
            et0=2.5,
            date_str="2026-11-25",
        )
        weather_service._cache_time = clock.farm_now()

        sug = await evaluate_weather_advisor(db, target_date="2026-11-25", force_refresh=True)
        assert sug is not None
        assert sug.feature == "weather_advisor"
        assert sug.status == "pending"
        assert "skip" in sug.action_payload_json.lower()
        assert sug.priority == "high"


@pytest.mark.asyncio
async def test_weather_advisor_heat_threshold(client):
    """Heat > 38°C or ET0 > 6.0mm triggers extend (+20%) recommendation."""
    async with async_session_factory() as db:
        weather_service._cached_forecast = _build_forecast_day(
            temp_max=41.0,
            precip_mm=0.0,
            precip_prob=0.0,
            et0=7.2,
            date_str="2026-11-26",
        )
        weather_service._cache_time = clock.farm_now()

        sug = await evaluate_weather_advisor(db, target_date="2026-11-26", force_refresh=True)
        assert sug is not None
        assert sug.status == "pending"
        assert "extend" in sug.action_payload_json.lower()
        assert "1.2" in sug.action_payload_json


@pytest.mark.asyncio
async def test_weather_advisor_normal_conditions_no_suggestion(client):
    """Normal weather conditions trigger no suggestion."""
    async with async_session_factory() as db:
        weather_service._cached_forecast = _build_forecast_day(
            temp_max=27.0,
            precip_mm=0.0,
            precip_prob=10.0,
            et0=4.0,
        )
        weather_service._cache_time = clock.farm_now()

        sug = await evaluate_weather_advisor(db, force_refresh=False)
        assert sug is None


@pytest.mark.asyncio
async def test_advisor_approval_creates_override(client):
    """Approving creates a ProgramOverride in DB and marks suggestion approved."""
    async with async_session_factory() as db:
        weather_service._cached_forecast = _build_forecast_day(
            temp_max=22.0,
            precip_mm=6.0,
            precip_prob=80.0,
            et0=2.0,
        )
        weather_service._cache_time = clock.farm_now()

        sug = await evaluate_weather_advisor(db, force_refresh=False)
        assert sug is not None

        override = await approve_suggestion(db, sug.id, operator_name="admin")
        assert override is not None
        assert override.action == "skip"
        assert override.applied is False
        assert override.suggestion_id == sug.id

        # Verify DB state
        saved_sug = await db.get(AISuggestion, sug.id)
        assert saved_sug.status == "approved"
        assert saved_sug.responded_by == "admin"


@pytest.mark.asyncio
async def test_advisor_rejection(client):
    """Rejecting marks status rejected and creates no override."""
    async with async_session_factory() as db:
        weather_service._cached_forecast = _build_forecast_day(
            temp_max=40.0,
            precip_mm=0.0,
            precip_prob=0.0,
            et0=6.5,
        )
        weather_service._cache_time = clock.farm_now()

        sug = await evaluate_weather_advisor(db, force_refresh=False)
        assert sug is not None

        rejected = await reject_suggestion(db, sug.id, operator_name="operator")
        assert rejected.status == "rejected"

        res = await db.execute(
            select(ProgramOverride).where(ProgramOverride.suggestion_id == sug.id)
        )
        assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_scheduler_honors_skip_override(client):
    """Scheduler encounters approved skip override: skips program and marks override applied."""
    scheduler.reset()
    tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(tz)
    today_str = now.strftime("%Y-%m-%d")
    t_0755 = datetime(now.year, now.month, now.day, 7, 55, tzinfo=tz)
    t_0805 = datetime(now.year, now.month, now.day, 8, 5, tzinfo=tz)

    original_now = clock.farm_now
    clock.farm_now = lambda: t_0805

    try:
        async with async_session_factory() as db:
            # Create program starting at 08:00
            prog = Program(
                id="prog_weather_skip",
                name="Morning Olive Irrigation",
                enabled=True,
                start_time_local="08:00",
                weekday_mask="1,2,3,4,5,6,7",
            )
            step = ProgramStep(
                id="step_skip_1",
                program_id=prog.id,
                zone_id="zone_rumman_1",
                step_order=1,
                duration_min=30,
            )
            prog.steps.append(step)
            db.add(prog)

            # Create approved skip override
            override = ProgramOverride(
                id="ovr_skip_test",
                program_id=prog.id,
                target_date=today_str,
                action="skip",
                duration_factor=0.0,
                applied=False,
                created_at=t_0755,
            )
            db.add(override)
            await db.commit()

            scheduler._last_farm_time = t_0755
            # Scheduler ticks
            await scheduler.tick(db, {})

            # Verify override was marked applied
            ovr_db = await db.get(ProgramOverride, override.id)
            assert ovr_db.applied is True
            assert ovr_db.applied_at is not None

            # Verify no active program started in scheduler state
            st = await scheduler._get_state(db, "scheduler.active_program")
            assert st is None
    finally:
        clock.farm_now = original_now


@pytest.mark.asyncio
async def test_scheduler_honors_extend_override(client):
    """Scheduler encounters approved extend override: multiplies duration by factor 1.2."""
    from conftest import push_state

    push_state(client)
    scheduler.reset()
    tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(tz)
    today_str = now.strftime("%Y-%m-%d")
    t_0655 = datetime(now.year, now.month, now.day, 6, 55, tzinfo=tz)
    t_0705 = datetime(now.year, now.month, now.day, 7, 5, tzinfo=tz)

    original_now = clock.farm_now
    clock.farm_now = lambda: t_0705

    try:
        async with async_session_factory() as db:
            prog = Program(
                id="prog_weather_extend",
                name="Heatwave Citrus Irrigation",
                enabled=True,
                start_time_local="07:00",
                weekday_mask="1,2,3,4,5,6,7",
            )
            step = ProgramStep(
                id="step_ext_1",
                program_id=prog.id,
                zone_id="zone_rumman_1",
                step_order=1,
                duration_min=20,
            )
            prog.steps.append(step)
            db.add(prog)

            override = ProgramOverride(
                id="ovr_extend_test",
                program_id=prog.id,
                target_date=today_str,
                action="extend",
                duration_factor=1.2,
                applied=False,
                created_at=t_0655,
            )
            db.add(override)
            await db.commit()

            scheduler._last_farm_time = t_0655
            from app.services.live_state import load_snapshots

            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # Verify override applied
            ovr_db = await db.get(ProgramOverride, override.id)
            assert ovr_db.applied is True

            # Verify active program has duration_factor 1.2
            import json

            st_json = await scheduler._get_state(db, "scheduler.active_program")
            assert st_json is not None
            data = json.loads(st_json)
            assert data.get("duration_factor") == 1.2
    finally:
        clock.farm_now = original_now
