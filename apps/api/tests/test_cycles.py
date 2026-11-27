"""Tests for irrigation cycle logging and endpoints (/api/v1/cycles)."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import login, push_state
from sqlalchemy import select

from app.core.clock import clock
from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.services.cycles import (
    record_cycle_end_for_zone,
)
from app.services.telemetry import (
    integrate_flow,
)


@pytest.mark.asyncio
async def test_cycle_lifecycle_and_water_integration(client):
    push_state(client)
    admin = login(client, "admin")

    # Start a zone run
    start_resp = client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
    )
    assert start_resp.status_code == 201

    # Check open cycle exists
    async with async_session_factory() as db:
        cyc_res = await db.execute(
            select(IrrigationCycle).where(
                IrrigationCycle.zone_id == "zone_enab",
                IrrigationCycle.actual_end_at.is_(None),
            )
        )
        open_cycle = cyc_res.scalars().first()
        assert open_cycle is not None
        assert open_cycle.outcome is None
        start_time = open_cycle.actual_start_at

        # Add simulated flow telemetry points spaced by 10s (within max_gap_s limit)
        t1 = start_time + timedelta(seconds=10)
        t2 = start_time + timedelta(seconds=20)
        t3 = start_time + timedelta(seconds=30)
        db.add_all(
            [
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_01",
                    zone_id="zone_enab",
                    ts=t1,
                    value_numeric=12.0,
                    value_text="1.0",
                ),
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_01",
                    zone_id="zone_enab",
                    ts=t2,
                    value_numeric=12.0,
                    value_text="1.0",
                ),
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_01",
                    zone_id="zone_enab",
                    ts=t3,
                    value_numeric=12.0,
                    value_text="1.0",
                ),
            ]
        )
        await db.commit()

        # Advance clock and close cycle
        clock_farm = start_time + timedelta(minutes=30)
        original_fn = clock.farm_now
        clock.farm_now = lambda: clock_farm

        try:
            closed = await record_cycle_end_for_zone(db, "zone_enab", outcome="completed")
            assert closed is not None
            assert closed.outcome == "completed"
            assert closed.actual_duration_min == 30
            assert closed.water_estimate_m3 > 0
            assert closed.water_is_estimate is False
            assert closed.water_has_gaps is True  # Only a short part of the run was observed.
            await db.commit()
        finally:
            clock.farm_now = original_fn

    # Test GET /api/v1/cycles
    get_res = client.get("/api/v1/cycles?zone_id=zone_enab", headers=admin)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["total"] >= 1
    assert data["items"][0]["zone_id"] == "zone_enab"
    assert data["items"][0]["outcome"] == "completed"

    # Test GET /api/v1/cycles/recent/zone_enab
    recent_res = client.get("/api/v1/cycles/recent/zone_enab", headers=admin)
    assert recent_res.status_code == 200
    recent_items = recent_res.json()
    assert len(recent_items) >= 1
    assert recent_items[0]["zone_id"] == "zone_enab"


@pytest.mark.asyncio
async def test_missing_water_with_no_samples(client):
    push_state(client)
    admin = login(client, "admin")

    start_resp = client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_zaytoun"},
    )
    assert start_resp.status_code == 201

    async with async_session_factory() as db:
        # Close without flow telemetry.
        closed = await record_cycle_end_for_zone(db, "zone_zaytoun", outcome="completed")
        assert closed is not None
        assert closed.outcome == "completed"
        assert closed.water_is_estimate is False
        assert closed.water_has_gaps is True
        assert closed.water_estimate_m3 is None
        await db.commit()

    resp = client.get("/api/v1/cycles?zone_id=zone_zaytoun", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["water_is_estimate"] is False
    assert data["items"][0]["water_has_gaps"] is True


@pytest.mark.asyncio
async def test_command_failure_or_supersede_aborts_open_cycle(client):
    push_state(client)
    admin = login(client, "admin")

    start_resp = client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
    )
    assert start_resp.status_code == 201
    cmd_id = start_resp.json()["id"]

    # Fail the command via sync_command
    from app.schemas.command import CommandSyncUpdate
    from app.services.commands import sync_command

    async with async_session_factory() as db:
        sync_req = CommandSyncUpdate(
            status="failed",
            failure_reason="PLC valve timeout",
        )
        updated_cmd = await sync_command(db, cmd_id, sync_req)
        assert updated_cmd.status == "failed"

        # Verify the open cycle was closed as aborted
        cyc_res = await db.execute(
            select(IrrigationCycle).where(
                IrrigationCycle.command_id == cmd_id,
            )
        )
        cycle = cyc_res.scalars().one()
        assert cycle.outcome == "aborted"
        assert cycle.failure_reason == "PLC valve timeout"
        assert cycle.actual_end_at is not None
        await db.commit()


@pytest.mark.asyncio
async def test_reset_and_back_to_real_leaves_no_open_cycles(client):
    push_state(client)
    admin = login(client, "admin")

    # Start a zone to open a cycle
    client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
    )

    # Call reset to real time
    resp = client.post(
        "/api/v1/sim/clock",
        headers=admin,
        json={"real": True, "confirm": True},
    )
    assert resp.status_code == 200

    async with async_session_factory() as db:
        res = await db.execute(
            select(IrrigationCycle).where(IrrigationCycle.actual_end_at.is_(None))
        )
        open_cycles = res.scalars().all()
        assert len(open_cycles) == 0


@pytest.mark.asyncio
async def test_timed_out_start_closes_cycle_as_aborted(client):
    """Regression: a start nobody picks up must not leave its cycle open forever."""
    push_state(client)
    admin = login(client, "admin")
    resp = client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
    )
    assert resp.status_code == 201
    cmd_id = resp.json()["id"]

    from app.core.timeutil import utcnow
    from app.models.command import Command
    from app.services.commands import expire_stale_commands

    async with async_session_factory() as db:
        cmd = await db.get(Command, cmd_id)
        cmd.requested_at_real = utcnow() - timedelta(minutes=10)
        await db.commit()
        expired = await expire_stale_commands(db)
        assert cmd_id in [c.id for c in expired]
        cycle = (
            (await db.execute(select(IrrigationCycle).where(IrrigationCycle.command_id == cmd_id)))
            .scalars()
            .one()
        )
        assert cycle.outcome == "aborted"
        assert cycle.actual_end_at is not None
        assert "No response from controller" in (cycle.failure_reason or "")


@pytest.mark.asyncio
async def test_zero_flow_run_uses_no_water(client):
    """Regression: measured zero flow (valve never opened) must not be replaced by nominal flow."""
    from app.services.cycles import integrate_zone_water_m3

    start = clock.farm_now()
    async with async_session_factory() as db:
        for i in range(3):
            db.add(
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_01",
                    zone_id="zone_enab",
                    ts=start + timedelta(seconds=10 * i),
                    value_numeric=0.0,
                    value_text="1.0",
                    source="simulator",
                )
            )
        await db.commit()
        volume = await integrate_zone_water_m3(
            db, "zone_enab", start, start + timedelta(seconds=20)
        )
    assert volume.m3 == 0.0 and not volume.is_estimate and not volume.has_gaps


@pytest.mark.asyncio
async def test_single_sample_is_flagged_estimate(client):
    from app.services.cycles import integrate_zone_water_m3

    start = clock.farm_now()
    async with async_session_factory() as db:
        db.add(
            TelemetryPoint(
                metric_key="zone.flow_m3h",
                farm_id="farm_01",
                zone_id="zone_rumman_1",
                ts=start + timedelta(seconds=30),
                value_numeric=6.0,
                value_text="1.0",
                source="simulator",
            )
        )
        await db.commit()
        volume = await integrate_zone_water_m3(
            db, "zone_rumman_1", start, start + timedelta(minutes=30)
        )
    assert volume.is_estimate and volume.has_gaps and volume.m3 == pytest.approx(3.0)


def test_only_real_breaks_count_as_missing_readings():
    start = datetime(2026, 11, 27, 8, 0, tzinfo=UTC)
    stop = start + timedelta(minutes=10)

    def volume(seconds):
        return integrate_flow(
            [(start + timedelta(seconds=s), 6.0, "1", "good") for s in seconds], start, stop
        )

    # a clean run: sampled every 10 s, never exactly on the first or last second
    assert not volume(range(7, 597, 10)).has_gaps(start, stop)
    # a break in the middle, a late first reading and an early last reading all count
    assert volume([*range(7, 200, 10), *range(400, 597, 10)]).has_gaps(start, stop)
    assert volume(range(40, 597, 10)).has_gaps(start, stop)
    assert volume(range(7, 560, 10)).has_gaps(start, stop)
    # one skipped sample at the end is still a clean run
    assert not volume(range(7, 580, 10)).has_gaps(start, stop)
    assert volume([]).has_gaps(start, stop)
