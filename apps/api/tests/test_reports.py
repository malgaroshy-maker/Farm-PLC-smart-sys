"""Tests for report endpoints and CSV exports (/api/v1/reports)."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import login, push_state

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle


@pytest.fixture
def seeded_cycles(client):
    """Seed test cycles for reports."""
    push_state(client)
    now = clock.farm_now()

    # Insert 2 cycles
    import asyncio

    async def _seed():
        async with async_session_factory() as db:
            c1 = IrrigationCycle(
                id="cyc_test_01",
                zone_id="zone_enab",
                source_mode="tank",
                planned_start_at=now,
                actual_start_at=now,
                actual_end_at=now + timedelta(minutes=40),
                planned_duration_min=40,
                actual_duration_min=40,
                outcome="completed",
                water_estimate_m3=8.5,
                initiated_by_type="user",
                created_at=now,
                updated_at=now,
            )
            c2 = IrrigationCycle(
                id="cyc_test_02",
                zone_id="zone_fruit_mix",
                source_mode="tank",
                planned_start_at=now - timedelta(days=1),
                actual_start_at=now - timedelta(days=1),
                actual_end_at=now - timedelta(days=1) + timedelta(minutes=30),
                planned_duration_min=30,
                actual_duration_min=30,
                outcome="completed",
                water_estimate_m3=6.2,
                initiated_by_type="scheduler",
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
            )
            db.add_all([c1, c2])
            await db.commit()

    asyncio.run(_seed())


def test_daily_irrigation_report(client, seeded_cycles):
    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/daily-irrigation", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Default is 7 inclusive days (today - 6 to today)
    assert len(data) == 7
    for row in data:
        assert "date" in row
        assert "total_water_m3" in row
        assert "cycle_count" in row
        assert "completed_count" in row
        assert "aborted_count" in row
        assert "skipped_count" in row
        # Sum of breakdown must strictly equal cycle_count
        breakdown_sum = (
            row["completed_count"]
            + row["aborted_count"]
            + row["skipped_count"]
            + row["faulted_count"]
            + row["manual_stop_count"]
        )
        assert row["cycle_count"] == breakdown_sum


def test_reports_date_range_filtering_and_presets(client, seeded_cycles):
    admin = login(client, "admin")
    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz).date()
    today_str = now.isoformat()

    # Preset Today: exactly 1 day
    resp_today = client.get(
        f"/api/v1/reports/daily-irrigation?from_date={today_str}&to_date={today_str}",
        headers=admin,
    )
    assert resp_today.status_code == 200
    data_today = resp_today.json()
    assert len(data_today) == 1
    assert data_today[0]["date"] == today_str

    # Preset 7 days: exactly 7 days
    from_7 = (now - timedelta(days=6)).isoformat()
    resp_7 = client.get(
        f"/api/v1/reports/daily-irrigation?from_date={from_7}&to_date={today_str}",
        headers=admin,
    )
    assert resp_7.status_code == 200
    assert len(resp_7.json()) == 7

    # Alias compatibility: ?from=...&to=... works too
    resp_alias = client.get(
        f"/api/v1/reports/daily-irrigation?from={from_7}&to={today_str}",
        headers=admin,
    )
    assert resp_alias.status_code == 200
    assert len(resp_alias.json()) == 7


def test_water_usage_report_and_csv_english(client, seeded_cycles):
    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/water-usage?format=csv", headers=admin)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    content_bytes = resp.content
    # Must start with UTF-8 BOM
    assert content_bytes.startswith(b"\xef\xbb\xbf")
    text = content_bytes.decode("utf-8")
    assert "Zone ID" in text
    assert "zone_enab" in text


def test_water_usage_report_csv_arabic(client, seeded_cycles):
    admin = login(client, "admin")
    # Request Arabic headers
    resp = client.get(
        "/api/v1/reports/water-usage?format=csv&lang=ar",
        headers={**admin, "Accept-Language": "ar"},
    )
    assert resp.status_code == 200
    content_bytes = resp.content
    assert content_bytes.startswith(b"\xef\xbb\xbf")
    text = content_bytes.decode("utf-8")
    # Must have Arabic header
    assert "معرف المنطقة" in text
    assert "إجمالي المياه" in text


def test_pump_runtime_report(client, seeded_cycles):
    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/pump-runtime", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "pump_id" in data[0]
    assert "runtime_hours" in data[0]
    assert "start_count" in data[0]
    assert "faults_count" in data[0]


def test_alarm_history_report(client, seeded_cycles):
    import asyncio

    from app.models.alarm import Alarm

    # Seed an alarm to ensure grouped results
    now = clock.farm_now()

    async def _seed_alarm():
        async with async_session_factory() as db:
            alm = Alarm(
                id="alm_test_01",
                alarm_code="ALM-001",
                severity="S3",
                category="equipment",
                status="active_unacked",
                triggered_at=now,
                message_en="Low Tank",
                message_ar="مستوى خزان منخفض",
            )
            db.add(alm)
            await db.commit()

    asyncio.run(_seed_alarm())

    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/alarm-history", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "alarm_code" in first
    assert "count" in first
    assert "severity" in first
    assert "title" in first
    assert "title_ar" in first
    assert first["count"] >= 1
    assert isinstance(data, list)
