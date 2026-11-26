"""Tests for report endpoints and CSV exports (/api/v1/reports)."""

import csv
import io
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import login, push_state

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.routers.reports import _csv_response
from app.services import pump_history


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


@pytest.mark.asyncio
async def test_reports_include_farm_midnight_and_exclude_generated_baselines(client):
    start = datetime(2030, 1, 1, 22, tzinfo=UTC)  # 00:00 the next day in Tripoli
    async with async_session_factory() as db:
        for cycle_id, when, volume in (
            ("cyc_test_before", start - timedelta(seconds=1), 3.0),
            ("cyc_test_at_midnight", start, 1.5),
            ("cyc_base_fixture", start + timedelta(minutes=1), 4.0),
            ("cyc_test_next_day", start + timedelta(days=1), 8.0),
        ):
            db.add(
                IrrigationCycle(
                    id=cycle_id,
                    zone_id="zone_enab",
                    actual_start_at=when,
                    outcome="completed",
                    water_estimate_m3=volume,
                )
            )
        await db.commit()

    admin = login(client, "admin")
    date_filter = "from_date=2030-01-02&to_date=2030-01-02"
    daily = client.get(f"/api/v1/reports/daily-irrigation?{date_filter}", headers=admin)
    assert daily.status_code == 200
    assert [(row["cycle_count"], row["total_water_m3"]) for row in daily.json()] == [(1, 1.5)]
    usage = client.get(
        f"/api/v1/reports/water-usage?{date_filter}&zone_id=zone_enab", headers=admin
    )
    assert usage.status_code == 200
    assert usage.json()[0]["total_water_m3"] == 1.5


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


def test_csv_keeps_zone_labels_literal_and_signed_numbers_numeric():
    response = _csv_response([["+ North Field", "  @ محطة", -0.5, 1]], "test.csv")
    rows = list(csv.reader(io.StringIO(response.body.decode("utf-8-sig"))))
    assert rows == [["'+ North Field", "'  @ محطة", "-0.5", "1"]]


def test_pump_runtime_report(client, seeded_cycles):
    admin = login(client, "admin")
    resp = client.get("/api/v1/reports/pump-runtime", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "pump_id" in data[0]
    assert all(row["runtime_hours"] is None and row["start_count"] is None for row in data)
    assert all(row["history_status"] == "unavailable" for row in data)


@pytest.mark.asyncio
async def test_water_today_clips_midnight_and_uses_valid_evidence_per_zone(client, monkeypatch):
    midnight = datetime(2030, 1, 1, 22, tzinfo=UTC)
    monkeypatch.setattr(clock, "farm_now", lambda *args: midnight + timedelta(minutes=3))
    async with async_session_factory() as db:
        for id_, zone, begin, end, water, estimated in (
            ("cyc_test_cross", "zone_enab", -10, 20, 9.0, True),
            ("cyc_test_known", "zone_rumman_1", 0, 65, 1.25, True),
            ("cyc_base_fixture", "zone_rumman_2", 0, 90, 8.0, False),
            ("cyc_test_future", "zone_zaytoun_2", 190, 240, 7.0, False),
        ):
            db.add(
                IrrigationCycle(
                    id=id_,
                    zone_id=zone,
                    actual_start_at=midnight + timedelta(seconds=begin),
                    actual_end_at=midnight + timedelta(seconds=end),
                    outcome="completed",
                    water_estimate_m3=water,
                    water_is_estimate=estimated,
                )
            )
        for zone, stamp, rate, source in (
            ("zone_enab", -10, 18.0, "simulator"),
            ("zone_enab", 20, 18.0, "simulator"),
            ("zone_zaytoun", 0, 18.0, "simulator"),
            ("zone_zaytoun", 10, 18.0, "simulator"),
            ("zone_zaytoun", 20, None, "simulator"),
            ("zone_zaytoun", 30, 18.0, "simulator"),
            ("zone_zaytoun", 40, 18.0, "simulator"),
            ("zone_zaytoun", 190, 900.0, "simulator"),
            ("zone_rumman_2", 30, 900.0, "simulator"),  # Legacy generated baseline sample.
            ("zone_rumman_2", 40, 18.0, "simulator"),  # A single reading supports no integral.
        ):
            db.add(
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id=settings.farm_id,
                    zone_id=zone,
                    ts=midnight + timedelta(seconds=stamp),
                    value_numeric=rate,
                    source=source,
                )
            )
        await db.commit()

    response = client.get("/api/v1/telemetry/water-today", headers=login(client, "viewer"))
    assert response.status_code == 200
    payload = response.json()
    rows = {row["zone_id"]: row["m3"] for row in payload["zones"]}
    assert rows == {
        "zone_enab": 0.1,
        "zone_rumman_1": 1.25,
        "zone_rumman_2": None,
        "zone_zaytoun": 0.1,
    }
    assert payload["total_m3"] == 1.45
    assert payload["water_has_gaps"] and payload["water_is_estimate"]


@pytest.mark.asyncio
async def test_water_totals_distinguish_absence_estimate_and_measured_zero(client, monkeypatch):
    moment = datetime(2030, 1, 2, 8, tzinfo=UTC)
    monkeypatch.setattr(clock, "farm_now", lambda *args: moment)
    async with async_session_factory() as db:
        for i, (zone, amount, estimated, has_gaps) in enumerate(
            [
                ("zone_enab", 0, True, False),
                ("zone_enab", 1.5, True, False),
                ("zone_zaytoun", 0, False, False),
                ("zone_rumman_2", 2.25, False, True),
            ]
        ):
            db.add(
                IrrigationCycle(
                    id=f"cyc_volume_case_{i}",
                    zone_id=zone,
                    actual_start_at=moment - timedelta(minutes=10),
                    actual_end_at=moment - timedelta(minutes=8),
                    outcome="completed",
                    water_estimate_m3=amount,
                    water_is_estimate=estimated,
                    water_has_gaps=has_gaps,
                )
            )
        await db.commit()

    headers = login(client, "operator")
    period = "from_date=2030-01-02&to_date=2030-01-02"
    water = client.get(f"/api/v1/reports/water-usage?{period}", headers=headers)
    assert water.status_code == 200
    rows = {row["zone_id"]: row for row in water.json()}
    assert rows["zone_enab"]["total_water_m3"] == 1.5
    assert rows["zone_enab"]["water_has_gaps"] and rows["zone_enab"]["water_is_estimate"]
    assert rows["zone_zaytoun"]["total_water_m3"] == 0
    assert not rows["zone_zaytoun"]["water_has_gaps"]
    assert rows["zone_rumman_1"]["total_water_m3"] is None
    assert rows["zone_rumman_2"]["total_water_m3"] == 2.25
    assert (
        rows["zone_rumman_2"]["water_has_gaps"] and not rows["zone_rumman_2"]["water_is_estimate"]
    )

    # List/read paths preserve the distinction for old stored estimated-zero placeholders.
    cycles = client.get("/api/v1/cycles?zone_id=zone_enab", headers=headers).json()["items"]
    unknown = next(row for row in cycles if row["id"] == "cyc_volume_case_0")
    assert unknown["water_estimate_m3"] is None
    assert unknown["water_has_gaps"] and not unknown["water_is_estimate"]


def test_pump_runtime_uses_observed_feedback_and_clips_gaps_and_midnight(client, monkeypatch):
    from conftest import SIM

    midnight = datetime(2030, 1, 1, 22, tzinfo=UTC)
    receipt = midnight
    monkeypatch.setattr(clock, "mode", "real")
    monkeypatch.setattr(clock, "farm_now", lambda *args: receipt)
    monkeypatch.setattr(pump_history, "utcnow", lambda: receipt)
    monkeypatch.setattr(settings, "deployment_mode", "simulation")
    monkeypatch.setattr(settings, "state_stale_after_sec", 5.0)
    pump_id = "pump_well_01"

    def send(seconds, running, *, sample_seconds=None, observed=True):
        nonlocal receipt
        receipt = midnight + timedelta(seconds=seconds)
        stamp = midnight + timedelta(
            seconds=sample_seconds if sample_seconds is not None else seconds
        )
        response = client.post(
            "/api/v1/state/sync",
            json=[
                {
                    "device_key": f"pump_{pump_id}",
                    "updated_at": stamp.isoformat(),
                    "state_json": {
                        "pump_id": pump_id,
                        "state": "running" if running else "stopped",
                        "run_fb": running,
                        "run_fb_observed": observed,
                        "last_updated": stamp.isoformat(),
                    },
                }
            ],
            headers=SIM,
        )
        assert response.status_code == 200

    send(-6, False)
    send(-3, True)
    send(1, True)
    send(4, False)
    send(30, True)  # Reconnected while running, so this is not an observed start.
    send(31, False, observed=False)  # The adapter could not read the real feedback.
    send(34, False)
    send(36, True)
    send(37, False, sample_seconds=36)  # Older or repeated packets do not rewrite history.
    send(40, False)
    receipt += timedelta(seconds=1)

    headers = login(client, "operator")
    path = f"/api/v1/reports/pump-runtime?from=2030-01-02&to=2030-01-02&pump_id={pump_id}"
    report = client.get(path, headers=headers)
    assert report.status_code == 200
    [row] = report.json()
    assert row["history_status"] == "partial" and row["history_source"] == "simulation"
    assert row["observed_seconds"] == 10 and row["window_seconds"] == 41
    assert row["runtime_hours"] == round(8 / 3600, 4) and row["start_count"] == 1

    export = client.get(path + "&format=csv", headers=headers)
    columns, values = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
    assert dict(zip(columns, values, strict=True))["History coverage"] == "partial"

    monkeypatch.setattr(settings, "deployment_mode", "local_pilot")
    monkeypatch.setattr(settings, "controller_mode", "plc")
    [field_row] = client.get(path, headers=headers).json()
    assert field_row["history_source"] == "controller" and field_row["runtime_hours"] is None


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
