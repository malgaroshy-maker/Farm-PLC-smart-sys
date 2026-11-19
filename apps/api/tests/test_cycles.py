"""Tests for irrigation cycle logging and endpoints (/api/v1/cycles)."""

from datetime import timedelta

import pytest
from conftest import login, push_state
from sqlalchemy import select

from app.core.clock import clock
from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle
from app.models.telemetry import TelemetryPoint
from app.services.cycles import (
    record_cycle_end_for_zone,
    record_cycles_aborted_on_jump,
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
async def test_clock_jump_aborts_active_cycles(client):
    push_state(client)
    admin = login(client, "admin")

    client.post(
        "/api/v1/commands",
        headers=admin,
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
    )

    async with async_session_factory() as db:
        jump_time = clock.farm_now() + timedelta(hours=3)
        aborted = await record_cycles_aborted_on_jump(db, jump_time)
        assert len(aborted) >= 1
        assert aborted[0].outcome == "aborted"
        assert aborted[0].failure_reason == "clock jump"
        await db.commit()
