"""Tests for the virtual farm clock scheduler (apps/api/app/services/scheduler.py)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import login, push_state
from sqlalchemy import select

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory
from app.models.command import Command
from app.models.event_log import EventLog
from app.models.irrigation_cycle import IrrigationCycle
from app.services.live_state import load_snapshots
from app.services.scheduler import (
    STATE_ACTIVE_PROGRAM,
    STATE_LAST_FARM_TIME,
    scheduler,
)


def _create_test_program(client, name="Test Program", start_time="08:00", zone="zone_enab"):
    admin = login(client, "admin")
    resp = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": name,
            "start_time_local": start_time,
            "weekday_mask": "1,2,3,4,5,6,7",
            "steps": [{"zone_id": zone, "step_order": 1, "duration_min": 20}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_scheduler_fires_once_when_due(client):
    push_state(client)
    _ = _create_test_program(client, "Fires Once", "08:00")

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_0755 = datetime(now.year, now.month, now.day, 7, 55, tzinfo=farm_tz)
    today_0805 = datetime(now.year, now.month, now.day, 8, 5, tzinfo=farm_tz)

    original_fn = clock.farm_now
    clock.farm_now = lambda: today_0805

    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler._last_farm_time = today_0755
            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # Check that a command was issued
            res = await db.execute(
                select(Command).where(
                    Command.target_id == "zone_enab",
                    Command.actor_type == "scheduler",
                )
            )
            cmds = res.scalars().all()
            assert len(cmds) == 1
            assert cmds[0].command_type == "start_zone"

            # Tick a second time at 08:10 -> should NOT fire again today
            today_0810 = datetime(now.year, now.month, now.day, 8, 10, tzinfo=farm_tz)
            clock.farm_now = lambda: today_0810
            await scheduler.tick(db, snaps)

            res2 = await db.execute(
                select(Command).where(
                    Command.target_id == "zone_enab",
                    Command.actor_type == "scheduler",
                )
            )
            assert len(res2.scalars().all()) == 1
    finally:
        clock.farm_now = original_fn


@pytest.mark.asyncio
async def test_scheduler_paused_does_not_fire(client):
    push_state(client)
    _create_test_program(client, "Paused Prog", "09:00")

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_0905 = datetime(now.year, now.month, now.day, 9, 5, tzinfo=farm_tz)

    clock.speed = 0.0
    original_fn = clock.farm_now
    clock.farm_now = lambda: today_0905
    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler._last_farm_time = datetime(
                now.year, now.month, now.day, 8, 55, tzinfo=farm_tz
            )
            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            res = await db.execute(select(Command).where(Command.actor_type == "scheduler"))
            assert len(res.scalars().all()) == 0
    finally:
        clock.speed = 1.0
        clock.farm_now = original_fn


@pytest.mark.asyncio
async def test_scheduler_missed_run_on_jump(client):
    push_state(client)
    prog_id = _create_test_program(client, "Missed Prog", "10:00")

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_0800 = datetime(now.year, now.month, now.day, 8, 0, tzinfo=farm_tz)
    today_1200 = datetime(now.year, now.month, now.day, 12, 0, tzinfo=farm_tz)

    original_fn = clock.farm_now
    clock.farm_now = lambda: today_1200

    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler.on_clock_jump(today_1200, today_0800)
            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # Missed rule: should NOT fire command!
            res = await db.execute(select(Command).where(Command.actor_type == "scheduler"))
            assert len(res.scalars().all()) == 0

            # Should log schedule.missed event
            ev_res = await db.execute(
                select(EventLog).where(
                    EventLog.event_type == "schedule.missed",
                    EventLog.entity_id == prog_id,
                )
            )
            events = ev_res.scalars().all()
            assert len(events) >= 1
    finally:
        clock.farm_now = original_fn


@pytest.mark.asyncio
async def test_scheduler_blocked_start_skips_and_continues(client):
    # Set state with low tank level (< 15%) which triggers tank_critically_low interlock for zone_rumman_1
    push_state(client, tank=5.0)
    admin = login(client, "admin")
    resp = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Multi Step Blocked",
            "start_time_local": "11:00",
            "weekday_mask": "1,2,3,4,5,6,7",
            "steps": [
                {"zone_id": "zone_rumman_1", "step_order": 1, "duration_min": 15},
                {"zone_id": "zone_enab", "step_order": 2, "duration_min": 20},
            ],
        },
    )
    assert resp.status_code == 201

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_1055 = datetime(now.year, now.month, now.day, 10, 55, tzinfo=farm_tz)
    today_1105 = datetime(now.year, now.month, now.day, 11, 5, tzinfo=farm_tz)

    original_fn = clock.farm_now
    clock.farm_now = lambda: today_1105

    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler._last_farm_time = today_1055
            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # Blocked start rule:
            # 1. Skipped cycle logged for zone_rumman_1
            cyc_res = await db.execute(
                select(IrrigationCycle).where(
                    IrrigationCycle.zone_id == "zone_rumman_1",
                    IrrigationCycle.outcome == "skipped",
                )
            )
            skipped_cycles = cyc_res.scalars().all()
            assert len(skipped_cycles) >= 1

            # 2. Event schedule.skipped logged
            ev_res = await db.execute(
                select(EventLog).where(EventLog.event_type == "schedule.skipped")
            )
            assert len(ev_res.scalars().all()) >= 1

            # 3. ALM-045 raised (Scheduled step skipped), ALM-035 NEVER raised
            from app.models.alarm import Alarm

            alm_45 = (
                (await db.execute(select(Alarm).where(Alarm.alarm_code == "ALM-045")))
                .scalars()
                .all()
            )
            assert len(alm_45) >= 1
            assert "Scheduled step skipped" in (alm_45[0].message_en or "") or "تخطي" in (
                alm_45[0].message_ar or ""
            )

            alm_35 = (
                (await db.execute(select(Alarm).where(Alarm.alarm_code == "ALM-035")))
                .scalars()
                .all()
            )
            assert len(alm_35) == 0

            # 4. Program continues to step 2 (zone_enab command submitted)
            cmd_res = await db.execute(
                select(Command).where(
                    Command.target_id == "zone_enab",
                    Command.actor_type == "scheduler",
                )
            )
            enab_cmds = cmd_res.scalars().all()
            assert len(enab_cmds) == 1
    finally:
        clock.farm_now = original_fn


@pytest.mark.asyncio
async def test_scheduler_late_tick_at_360x_fires_once_not_missed(client):
    push_state(client)
    _ = _create_test_program(client, "Late Tick 360x", "14:00", zone="zone_fruit_mix")

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_1350 = datetime(now.year, now.month, now.day, 13, 50, tzinfo=farm_tz)
    today_1410 = datetime(now.year, now.month, now.day, 14, 10, tzinfo=farm_tz)

    original_fn = clock.farm_now
    clock.farm_now = lambda: today_1410
    old_speed = clock.speed
    clock.speed = 360.0

    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler.reset()
            scheduler._last_farm_time = today_1350
            # Simulate a 5-second real delay (5s * 360 = 1800 farm s = 30 farm min)
            from app.core.timeutil import utcnow

            scheduler._last_real_time = utcnow() - timedelta(seconds=5)

            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # It must fire, NOT be marked as missed!
            res = await db.execute(
                select(Command).where(
                    Command.target_id == "zone_fruit_mix",
                    Command.actor_type == "scheduler",
                )
            )
            cmds = res.scalars().all()
            assert len(cmds) == 1
            assert cmds[0].command_type == "start_zone"

            # Should NOT log schedule.missed
            ev_res = await db.execute(
                select(EventLog).where(
                    EventLog.event_type == "schedule.missed",
                )
            )
            missed_events = [
                e
                for e in ev_res.scalars().all()
                if e.payload.get("program_name") == "Late Tick 360x"
            ]
            assert len(missed_events) == 0
    finally:
        clock.speed = old_speed
        clock.farm_now = original_fn


@pytest.mark.asyncio
async def test_scheduler_explicit_jump_marks_missed(client):
    push_state(client)
    prog_id = _create_test_program(client, "Explicit Jump Missed", "16:00", zone="zone_zaytoun")

    farm_tz = ZoneInfo(settings.farm_timezone)
    now = clock.farm_now().astimezone(farm_tz)
    today_1550 = datetime(now.year, now.month, now.day, 15, 50, tzinfo=farm_tz)
    today_1620 = datetime(now.year, now.month, now.day, 16, 20, tzinfo=farm_tz)

    original_fn = clock.farm_now
    clock.farm_now = lambda: today_1620

    try:
        async with async_session_factory() as db:
            await scheduler._clear_state(db, STATE_ACTIVE_PROGRAM)
            await scheduler._clear_state(db, STATE_LAST_FARM_TIME)
            scheduler.reset()
            # Explicit clock jump registered
            scheduler.on_clock_jump(today_1620, today_1550)

            snaps = await load_snapshots(db)
            await scheduler.tick(db, snaps)

            # Must NOT fire command
            res = await db.execute(
                select(Command).where(
                    Command.target_id == "zone_zaytoun",
                    Command.actor_type == "scheduler",
                )
            )
            assert len(res.scalars().all()) == 0

            # Must log schedule.missed event
            ev_res = await db.execute(
                select(EventLog).where(
                    EventLog.event_type == "schedule.missed",
                    EventLog.entity_id == prog_id,
                )
            )
            assert len(ev_res.scalars().all()) >= 1
    finally:
        clock.farm_now = original_fn
