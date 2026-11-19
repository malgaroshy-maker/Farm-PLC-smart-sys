"""Tests for report endpoints and CSV exports (/api/v1/reports)."""

from datetime import timedelta

import pytest
from conftest import login, push_state

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
    assert len(data) >= 2


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
    assert "total_runtime_hours" in data[0]


def test_alarm_history_report(client, seeded_cycles):
    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/alarm-history", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
