"""A program never resumes after a gap, and a stop is never silently dropped."""

import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import login, push_state
from sqlalchemy import select

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.models.ai import AISuggestion, ProgramOverride
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.event_log import EventLog
from app.routers.schedules import compute_upcoming_runs
from app.services import commands as command_service
from app.services.alarms import engine as alarm_engine
from app.services.live_state import load_snapshots
from app.services.scheduler import STATE_ACTIVE_PROGRAM, scheduler

TZ = ZoneInfo(settings.farm_timezone)


def at(hour, minute=0):
    now = datetime.now(TZ)
    return datetime(now.year, now.month, now.day, hour, minute, tzinfo=TZ)


def make_program(client, steps=("zone_enab", "zone_rumman_1"), start="08:00"):
    r = client.post(
        "/api/v1/schedules",
        headers=login(client, "admin"),
        json={
            "name": "Two Steps",
            "start_time_local": start,
            "weekday_mask": "1,2,3,4,5,6,7",
            "steps": [
                {"zone_id": z, "step_order": i + 1, "duration_min": 20} for i, z in enumerate(steps)
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def tick(monkeypatch, when):
    with monkeypatch.context() as m:
        m.setattr(clock, "farm_now", lambda real_now=None: when)
        async with async_session_factory() as db:
            await scheduler.tick(db, await load_snapshots(db))


async def active():
    async with async_session_factory() as db:
        return await scheduler._get_state(db, STATE_ACTIVE_PROGRAM)


async def rows(model, *where):
    async with async_session_factory() as db:
        return list((await db.execute(select(model).where(*where))).scalars())


async def start_program(client, monkeypatch):
    push_state(client)
    prog = make_program(client)
    scheduler.reset()
    scheduler._last_farm_time = at(7, 59)
    await tick(monkeypatch, at(8, 1))
    assert await active()
    return prog


async def cancel_reasons():
    events = await rows(EventLog, EventLog.event_type == "program.cancelled")
    return [json.loads(e.payload_json)["reason"] for e in events]


async def finish_first_command(age_sec=0):
    async with async_session_factory() as db:
        cmd = (await db.execute(select(Command))).scalars().one()
        cmd.status = "completed"
        cmd.requested_at_real = utcnow() - timedelta(seconds=age_sec)
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["disable", "automation", "edit", "downtime"])
async def test_program_is_cancelled_not_resumed(client, monkeypatch, change):
    prog = await start_program(client, monkeypatch)
    admin = login(client, "admin")
    expected = {
        "disable": "program_switched_off",
        "automation": "automation_switched_off",
        "edit": "program_edited",
        "downtime": "app_was_down",
    }[change]
    if change == "disable":
        r = client.patch(f"/api/v1/schedules/{prog}/toggle", headers=admin, json={"enabled": False})
        assert r.status_code == 200, r.text
    elif change == "edit":
        r = client.patch(
            f"/api/v1/schedules/{prog}",
            headers=admin,
            json={"steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 5}]},
        )
        assert r.status_code == 200, r.text
    elif change == "downtime":
        scheduler._last_real_time = utcnow() - timedelta(minutes=10)
    await finish_first_command(age_sec=60)  # the step looks finished: it must not advance
    if change == "automation":
        from app.services import features

        async def off(db, key):
            return key != "automation.scheduler"

        monkeypatch.setattr(features, "is_enabled", off)
    await tick(monkeypatch, at(8, 3))
    assert await active() is None
    assert len(await rows(Command)) == 1
    assert await cancel_reasons() == [expected]


@pytest.mark.asyncio
async def test_step_waits_until_the_controller_shows_the_zone(client, monkeypatch):
    await start_program(client, monkeypatch)
    await finish_first_command()  # a PLC accepted it; the snapshot still says off
    await tick(monkeypatch, at(8, 2))
    assert len(await rows(Command)) == 1
    push_state(client, zone_states={"zone_enab": "running"})
    await tick(monkeypatch, at(8, 3))
    push_state(client)
    await tick(monkeypatch, at(8, 22))
    assert sorted(c.target_id for c in await rows(Command)) == ["zone_enab", "zone_rumman_1"]


@pytest.mark.asyncio
async def test_accepted_start_counts_until_a_snapshot_shows_it(client):
    push_state(client)
    admin = login(client, "admin")

    def start(zone):
        return client.post(
            "/api/v1/commands",
            headers=admin,
            json={
                "command_type": "start_zone",
                "target_type": "zone",
                "target_id": zone,
                "payload": {"duration_min": 5},
            },
        )

    assert start("zone_enab").status_code == 201
    await finish_first_command()
    refused = start("zone_rumman_1")
    assert refused.status_code in (409, 422), refused.text


@pytest.mark.asyncio
async def test_a_stop_is_kept_until_confirmed_and_raises_an_alarm(client):
    push_state(client)
    r = client.post(
        "/api/v1/commands",
        headers=login(client, "admin"),
        json={"command_type": "stop_all", "target_type": "system"},
    )
    assert r.status_code == 201, r.text
    async with async_session_factory() as db:
        cmd = (await db.execute(select(Command))).scalars().one()
        cmd.requested_at = utcnow() - timedelta(hours=1)
        cmd.requested_at_real = utcnow() - timedelta(hours=1)
        await db.commit()
        await command_service.expire_stale_commands(db)
        await db.commit()
        await alarm_engine.on_monitor_tick(db, await load_snapshots(db))
        await db.commit()
    assert (await rows(Command))[0].status == "pending"
    assert len(await rows(Alarm, Alarm.alarm_code == "ALM-052")) == 1


@pytest.mark.asyncio
async def test_upcoming_runs_follow_one_day_changes(client):
    prog = make_program(client, steps=("zone_enab",), start="23:59")
    async with async_session_factory() as db:
        first = (await compute_upcoming_runs(db, hours=24))[0]
        day = first.scheduled_start_farm[:10]
        change = ProgramOverride(
            id="override_test",
            program_id=prog,
            target_date=day,
            action="reduce",
            duration_factor=0.5,
            created_at=utcnow(),
        )
        db.add(change)
        await db.commit()
        assert (await compute_upcoming_runs(db, hours=24))[0].duration_min == 10
        change.action = "skip"
        await db.commit()
        left = await compute_upcoming_runs(db, hours=24)
        assert not [r for r in left if r.scheduled_start_farm[:10] == day]


@pytest.mark.asyncio
async def test_tick_does_not_wait_for_the_morning_briefing(client, monkeypatch):
    """The briefing waits on the AI: it must not keep the database locked against STOP ALL."""
    push_state(client)
    gate = asyncio.Event()

    async def slow_briefing(db, **_):
        await gate.wait()

    from app.services.ai import briefing

    monkeypatch.setattr(briefing, "check_scheduled_briefing", slow_briefing)
    scheduler.reset()
    scheduler._last_farm_time = at(5, 59)
    monkeypatch.setattr(clock, "farm_now", lambda real_now=None: at(6, 1))
    async with async_session_factory() as db:
        await asyncio.wait_for(scheduler.tick(db, await load_snapshots(db)), timeout=5)
        assert not db.in_transaction()
    gate.set()
    await asyncio.gather(*scheduler._background, return_exceptions=True)


@pytest.mark.asyncio
async def test_old_soil_advice_cannot_start_water_and_approval_can_be_undone(client):
    push_state(client)
    admin = login(client, "admin")
    async with async_session_factory() as db:
        db.add(
            AISuggestion(
                id="sug_old",
                feature="soil",
                priority="medium",
                status="pending",
                title="Extra run",
                description="dry",
                action_payload_json=json.dumps(
                    {"action": "extra_run", "zone_id": "zone_enab", "duration_min": 10}
                ),
                created_at=utcnow() - timedelta(hours=20),
                expires_at=clock.farm_now() - timedelta(hours=1),
            )
        )
        db.add(
            AISuggestion(
                id="sug_done",
                feature="weather_advisor",
                priority="medium",
                status="approved",
                title="Skip",
                description="rain",
                created_at=utcnow(),
            )
        )
        db.add(
            ProgramOverride(
                id="ovr_1",
                target_date="2099-01-01",
                action="skip",
                suggestion_id="sug_done",
                created_at=utcnow(),
            )
        )
        await db.commit()
    r = client.post("/api/v1/ai/suggestions/sug_old/approve", headers=admin)
    assert r.status_code == 409, r.text
    assert await rows(Command) == []
    r = client.post("/api/v1/ai/suggestions/sug_done/undo", headers=admin)
    assert r.status_code == 200, r.text
    assert await rows(ProgramOverride) == []
    assert (await rows(AISuggestion, AISuggestion.id == "sug_done"))[0].status == "pending"
