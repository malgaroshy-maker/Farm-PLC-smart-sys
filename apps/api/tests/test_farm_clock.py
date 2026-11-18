"""Tests for the virtual farm clock and timestamp adherence (SIMULATION_TIME.md)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import login

from app.config import settings
from app.core.clock import FarmClock, clock
from app.database import async_session_factory
from app.deps import Actor
from app.models.command import Command
from app.models.event_log import EventLog
from app.models.telemetry import TelemetryPoint
from app.services import alarms as alarm_svc
from app.services import commands as cmd_svc
from app.services import events as event_svc
from app.services import telemetry as telem_svc
from app.services.alarms import Condition


def test_clock_formula_and_reanchoring():
    c = FarmClock()
    t0 = datetime(2026, 11, 19, 10, 0, 0, tzinfo=UTC)
    c.anchor_real = t0
    c.anchor_sim = t0
    c.mode = "sim"
    c.speed = 10.0

    # At t0 + 5s real, farm time should be t0 + 50s
    t1 = t0 + timedelta(seconds=5)
    assert c.farm_now(t1) == t0 + timedelta(seconds=50)

    # Change speed to 60x: must re-anchor at t1 without jumping
    c.set_speed(60.0, real_now=t1)
    assert c.anchor_real == t1
    assert c.anchor_sim == t0 + timedelta(seconds=50)
    assert c.farm_now(t1) == t0 + timedelta(seconds=50)

    # At t1 + 2s real, farm time advances by 120s
    t2 = t1 + timedelta(seconds=2)
    assert c.farm_now(t2) == t0 + timedelta(seconds=50 + 120)


def test_clock_pause_and_step():
    c = FarmClock()
    t0 = datetime(2026, 11, 19, 10, 0, 0, tzinfo=UTC)
    c.anchor_real = t0
    c.anchor_sim = t0
    c.mode = "sim"
    c.speed = 10.0

    t1 = t0 + timedelta(seconds=5)
    c.pause(real_now=t1)
    assert c.is_paused
    assert c.speed == 0.0
    sim_paused = c.farm_now(t1)
    assert sim_paused == t0 + timedelta(seconds=50)

    # While paused, advancing real time does not advance farm time
    t2 = t1 + timedelta(seconds=100)
    assert c.farm_now(t2) == sim_paused

    # Step +1 min
    c.step(1.0, real_now=t2)
    assert c.farm_now(t2) == sim_paused + timedelta(minutes=1)

    # Resume: returns to last nonzero speed (10.0)
    c.resume(real_now=t2)
    assert c.speed == 10.0
    t3 = t2 + timedelta(seconds=1)
    assert c.farm_now(t3) == sim_paused + timedelta(minutes=1, seconds=10)


def test_clock_monotonic_jump():
    c = FarmClock()
    tz = ZoneInfo(settings.farm_timezone)
    # 08:00 local time
    local_0800 = datetime(2026, 11, 19, 8, 0, 0, tzinfo=tz)
    utc_0800 = local_0800.astimezone(UTC)

    c.anchor_real = utc_0800
    c.anchor_sim = utc_0800
    c.mode = "sim"
    c.speed = 1.0

    # Jump to 05:30: since 05:30 today is in the past, it must jump to 05:30 tomorrow
    prev_sim, next_sim = c.jump_to("05:30", real_now=utc_0800)
    assert prev_sim == utc_0800
    next_local = next_sim.astimezone(tz)
    assert next_local.hour == 5
    assert next_local.minute == 30
    assert next_local.day == 20  # tomorrow!
    assert next_sim > prev_sim

    # Jump to 12:00: since 05:30 tomorrow is before 12:00 tomorrow, it jumps to 12:00 on day 20
    prev_sim2, next_sim2 = c.jump_to("12:00", real_now=utc_0800)
    next_local2 = next_sim2.astimezone(tz)
    assert next_local2.hour == 12
    assert next_local2.minute == 0
    assert next_local2.day == 20


def test_locked_to_real_when_not_simulator(monkeypatch):
    c = FarmClock()
    monkeypatch.setattr(settings, "controller_mode", "plc")
    assert c.is_locked_real
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
    assert c.farm_now(now) == now

    with pytest.raises(ValueError, match="locked to real"):
        c.set_speed(10.0)

    with pytest.raises(ValueError, match="locked to real"):
        c.pause()

    with pytest.raises(ValueError, match="locked to real"):
        c.step(1.0)

    with pytest.raises(ValueError, match="locked to real"):
        c.jump_to("05:30")


@pytest.mark.asyncio
async def test_persistence_across_restart(client):
    c = FarmClock()
    t0 = datetime(2026, 11, 19, 6, 0, 0, tzinfo=UTC)
    c.anchor_real = t0
    c.anchor_sim = t0 + timedelta(hours=3)
    c.speed = 60.0
    c.mode = "sim"
    async with async_session_factory() as db:
        await c.save(db)

    # New clock instance loading from DB
    c2 = FarmClock()
    async with async_session_factory() as db:
        await c2.load(db)
    assert c2.mode == "sim"
    assert c2.speed == 60.0
    assert c2.anchor_sim == c.anchor_sim


@pytest.mark.asyncio
async def test_timestamps_use_farm_clock(client, monkeypatch):
    # Set simulated farm time to 2028-05-01 12:00:00 (far in future)
    sim_t = datetime(2028, 5, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "mode", "sim")
    monkeypatch.setattr(clock, "farm_now", lambda *args: sim_t)

    async with async_session_factory() as db:
        # 1. Event log
        await event_svc.log_event(db, "test.event", "system", "test", actor_type="system")
        await db.commit()
        ev = (await db.execute(EventLog.__table__.select())).first()
        from app.core.timeutil import as_utc

        assert as_utc(ev.occurred_at) == sim_t

        # 2. Alarm lifecycle
        cond = Condition("ALM-001", value=20.0, threshold=25.0)
        events = await alarm_svc.engine.reconcile(db, [cond], {"ALM-001"})
        assert len(events) == 1
        alarm = events[0][1]
        assert as_utc(alarm.triggered_at) == sim_t

        actor = Actor(actor_type="user", actor_id="admin_1", role="owner_admin", name="Admin")
        ack = await alarm_svc.engine.acknowledge(db, alarm.id, actor)
        assert as_utc(ack.acknowledged_at) == sim_t

        # 3. Telemetry points
        snaps = {
            "simulation_stats": type("Snap", (), {"state": {"tank_level_pct": 55.0}})(),
        }
        telem_svc.recorder._last_real = None
        telem_svc.recorder._last_farm = None
        recorded = await telem_svc.recorder.maybe_record(db, snaps)
        assert recorded > 0
        tp = (await db.execute(TelemetryPoint.__table__.select())).first()
        assert as_utc(tp.ts) == sim_t


@pytest.mark.asyncio
async def test_link_staleness_and_timeouts_stay_on_real_time(client, monkeypatch):
    # Even if farm clock is at 360x or in 2028:
    sim_t = datetime(2028, 5, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "mode", "sim")
    monkeypatch.setattr(clock, "speed", 360.0)
    monkeypatch.setattr(clock, "farm_now", lambda *args: sim_t)

    # Command timeouts:
    # A command requested 20 real seconds ago (pending timeout is 15s)
    real_now = datetime(2026, 11, 19, 10, 0, 20, tzinfo=UTC)
    real_req = datetime(2026, 11, 19, 10, 0, 0, tzinfo=UTC)
    cmd = Command(
        id="cmd_test_timeout",
        command_type="start_zone",
        target_type="zone",
        target_id="zone_rumman_1",
        requested_by=None,
        actor_type="user",
        status="pending",
        requested_at=sim_t,
        requested_at_real=real_req,
    )
    async with async_session_factory() as db:
        db.add(cmd)
        await db.commit()

        monkeypatch.setattr(cmd_svc, "utcnow", lambda: real_now)
        expired = await cmd_svc.expire_stale_commands(db)
        assert len(expired) == 1
        assert expired[0].id == "cmd_test_timeout"
        assert expired[0].status == "timed_out"
        assert expired[0].completed_at == sim_t  # user-facing completed_at in farm time!


def test_api_clock_endpoints(client):
    admin = login(client, "admin")
    viewer = login(client, "viewer")

    # 1. GET clock works for any user
    r = client.get("/api/v1/sim/clock", headers=viewer)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "farm_now" in data
    assert "speed" in data
    assert "mode" in data

    # 2. POST clock forbidden for viewer (admin only)
    r = client.post("/api/v1/sim/clock", json={"speed": 60}, headers=viewer)
    assert r.status_code == 403

    # 3. POST clock speed works for admin
    r = client.post("/api/v1/sim/clock", json={"speed": 60}, headers=admin)
    assert r.status_code == 200
    assert r.json()["speed"] == 60.0
    assert r.json()["mode"] == "sim"

    # 4. POST pause / resume
    r = client.post("/api/v1/sim/clock", json={"pause": True}, headers=admin)
    assert r.status_code == 200
    assert r.json()["paused"] is True
    assert r.json()["speed"] == 0.0

    r = client.post("/api/v1/sim/clock", json={"pause": False}, headers=admin)
    assert r.status_code == 200
    assert r.json()["paused"] is False
    assert r.json()["speed"] == 60.0

    # 5. POST step +1 min
    r = client.post("/api/v1/sim/clock", json={"step_min": 1}, headers=admin)
    assert r.status_code == 200

    # 6. POST jump to 05:30
    r = client.post("/api/v1/sim/clock", json={"jump_to": "05:30"}, headers=admin)
    assert r.status_code == 200

    # 7. POST back to real time without confirm -> 400
    r = client.post("/api/v1/sim/clock", json={"real": True}, headers=admin)
    assert r.status_code == 400

    # 8. POST back to real time with confirm -> clears history, resets to real at 1x
    r = client.post("/api/v1/sim/clock", json={"real": True, "confirm": True}, headers=admin)
    assert r.status_code == 200
    assert r.json()["mode"] == "real"
    assert r.json()["speed"] == 1.0

    # 9. POST clock allowed with simulator service token (sets initial timescale)
    service_headers = {"Authorization": f"Bearer {settings.simulator_token}"}
    r = client.post("/api/v1/sim/clock", json={"speed": 10}, headers=service_headers)
    assert r.status_code == 200
    assert r.json()["speed"] == 10.0
    assert r.json()["mode"] == "sim"


@pytest.mark.asyncio
async def test_reset_history_resets_clock():
    from app.models.clock import FarmClockModel
    from app.reset_demo import reset_history

    clock.set_speed(360.0)
    async with async_session_factory() as db:
        await clock.save(db)

    # Call reset_history (same as run.bat reset)
    await reset_history()

    assert clock.mode == "real"
    assert clock.speed == 1.0
    async with async_session_factory() as db:
        row = (await db.get(FarmClockModel, 1))
        assert row is not None
        assert row.mode == "real"
        assert row.speed == 1.0

