"""Tests for the virtual farm clock and timestamp adherence (SIMULATION_TIME.md)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import SIM, login, push_state

from app.config import settings
from app.core.clock import FarmClock, clock
from app.core.timeutil import utcnow
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
from app.services.live_state import Snapshot


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
            "simulation_stats": Snapshot({"tank_level_pct": 55.0}, utcnow()),
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

    # Link staleness check:
    # A snapshot updated 2 real seconds ago (staleness limit is 5s)
    # Even if farm clock is at 360x (where 2 real seconds = 12 farm minutes),
    # staleness must NOT trigger.
    from app.services.live_state import Snapshot

    snap_recent = {
        "zone_a": Snapshot(state={"state": "running"}, updated_at=real_req + timedelta(seconds=18))
    }
    stale_conds = alarm_svc.engine.staleness_conditions(snap_recent, real_now)
    assert len(stale_conds) == 0  # Only 2 real seconds elapsed -> NOT stale

    # After 6 real seconds without updates (limit is 5s):
    real_stale_now = real_req + timedelta(seconds=25)
    stale_conds_triggered = alarm_svc.engine.staleness_conditions(snap_recent, real_stale_now)
    assert any(c.code == "ALM-044" for c in stale_conds_triggered)


@pytest.mark.asyncio
async def test_alm036_and_water_today_follow_farm_time(client, monkeypatch):
    from app.models.alarm import Alarm

    # Farm time at t0
    t0 = datetime(2026, 11, 19, 10, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "mode", "sim")
    monkeypatch.setattr(clock, "farm_now", lambda *args: t0)

    async with async_session_factory() as db:
        # Seed 3 major faults on zone_enab at farm time t0
        for i in range(3):
            db.add(
                Alarm(
                    id=f"fault_alm_{i}",
                    alarm_code="ALM-019",
                    severity="S2",
                    category="hydraulic",
                    status="active_unacked",
                    zone_id="zone_enab",
                    source_layer="plc",
                    triggered_at=t0 - timedelta(hours=i),
                    correlation_key=f"ALM-019:zone_enab:{i}",
                )
            )
        await db.commit()

        # At t0: ALM-036 is raised because 3 faults occurred in the last 24 farm hours
        conds = await alarm_svc.engine.derived_conditions(db, {}, t0, utcnow())
        assert any(c.code == "ALM-036" and c.zone_id == "zone_enab" for c in conds)

        # Advance farm time by 25 farm hours:
        t_future = t0 + timedelta(hours=25)
        conds_future = await alarm_svc.engine.derived_conditions(db, {}, t_future, utcnow())
        # The 24-farm-hour window has passed -> ALM-036 is no longer triggered!
        assert not any(c.code == "ALM-036" and c.zone_id == "zone_enab" for c in conds_future)

    # Water-today resets at farm midnight:
    # 23:30 Tripoli time (21:30 UTC)
    t_night = datetime(2026, 11, 19, 21, 30, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "farm_now", lambda *args: t_night)
    midnight_before = telem_svc.farm_midnight_utc()

    # Cross farm midnight to 00:30 next day Tripoli time (22:30 UTC)
    t_next_day = datetime(2026, 11, 19, 22, 30, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "farm_now", lambda *args: t_next_day)
    midnight_after = telem_svc.farm_midnight_utc()

    assert midnight_after > midnight_before
    assert (midnight_after - midnight_before) == timedelta(days=1)


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

    # 5b. POST step with negative/zero step_min -> 422
    r = client.post("/api/v1/sim/clock", json={"step_min": -5}, headers=admin)
    assert r.status_code == 422
    r = client.post("/api/v1/sim/clock", json={"step_min": 0}, headers=admin)
    assert r.status_code == 422

    # 6. POST jump to 05:30
    r = client.post("/api/v1/sim/clock", json={"jump_to": "05:30"}, headers=admin)
    assert r.status_code == 200

    # 6b. POST jump with invalid time format -> 422
    r = client.post("/api/v1/sim/clock", json={"jump_to": "99:99"}, headers=admin)
    assert r.status_code == 422
    r = client.post("/api/v1/sim/clock", json={"jump_to": "invalid"}, headers=admin)
    assert r.status_code == 422

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
        row = await db.get(FarmClockModel, 1)
        assert row is not None
        assert row.mode == "real"
        assert row.speed == 1.0


def test_command_sync_at_360x_stamps_farm_time(client):
    op = login(client, "operator")
    push_state(client)
    clock.set_speed(360.0)

    # 1. Test two-step sync: pending -> in_progress -> completed
    r = client.post(
        "/api/v1/commands",
        json={"command_type": "start_zone", "target_type": "zone", "target_id": "zone_enab"},
        headers=op,
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    req_at = datetime.fromisoformat(r.json()["requested_at"])

    fake_real_time = "2026-11-19T06:00:00+00:00"
    # Step 1: Controller acknowledges
    r_ack = client.patch(
        f"/api/v1/commands/{cid}/sync",
        json={
            "status": "accepted",
            "acknowledged_at": fake_real_time,
        },
        headers=SIM,
    )
    assert r_ack.status_code == 200
    ack_data = r_ack.json()
    ack_at = datetime.fromisoformat(ack_data["acknowledged_at"])
    assert ack_at >= req_at
    assert ack_at.isoformat() != fake_real_time
    assert ack_data["completed_at"] is None

    # Step 2: Controller completes
    r_comp = client.patch(
        f"/api/v1/commands/{cid}/sync",
        json={
            "status": "completed",
            "completed_at": fake_real_time,
        },
        headers=SIM,
    )
    assert r_comp.status_code == 200
    comp_data = r_comp.json()
    comp_at = datetime.fromisoformat(comp_data["completed_at"])
    ack_at_final = datetime.fromisoformat(comp_data["acknowledged_at"])
    assert comp_at >= ack_at_final >= req_at
    assert comp_at.isoformat() != fake_real_time

    # 2. Test direct terminal sync (pending -> completed)
    r2 = client.post(
        "/api/v1/commands",
        json={"command_type": "stop_zone", "target_type": "zone", "target_id": "zone_enab"},
        headers=op,
    )
    assert r2.status_code == 201
    cid2 = r2.json()["id"]
    req_at2 = datetime.fromisoformat(r2.json()["requested_at"])

    r2_sync = client.patch(
        f"/api/v1/commands/{cid2}/sync",
        json={
            "status": "completed",
            "completed_at": fake_real_time,
            "acknowledged_at": fake_real_time,
        },
        headers=SIM,
    )
    assert r2_sync.status_code == 200
    synced2 = r2_sync.json()
    ack_at2 = datetime.fromisoformat(synced2["acknowledged_at"])
    comp_at2 = datetime.fromisoformat(synced2["completed_at"])
    assert ack_at2 >= req_at2
    assert comp_at2 >= req_at2
    assert comp_at2 >= ack_at2
    assert ack_at2.isoformat() != fake_real_time
    assert comp_at2.isoformat() != fake_real_time
    clock.reset_to_real()


@pytest.mark.asyncio
async def test_water_today_at_1x_drops_10min_outage(client, monkeypatch):
    monkeypatch.setattr("app.core.clock.utcnow", lambda: datetime(2026, 11, 24, 12, tzinfo=UTC))
    clock.reset_to_real()
    now = clock.farm_now()
    async with async_session_factory() as db:
        # Two points 10 s apart (6 m³/h for 10 s = 6 * 10 / 3600 = 0.01667 m³)
        # Then a 10-minute (600 s) outage gap
        # Then two points 10 s apart (6 * 10 / 3600 = 0.01667 m³)
        # Total integrated should be ~0.033 m³, NOT including the 600 s outage (~1.0 m³)
        for offset in [-620, -610, -10, 0]:
            db.add(
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_algaroshy",
                    zone_id="zone_enab",
                    ts=now + timedelta(seconds=offset),
                    value_numeric=6.0,
                    value_text="1.0",
                )
            )
        await db.commit()

        zones = await telem_svc.water_today(db)
        enab = next((z for z in zones if z["zone_id"] == "zone_enab"), None)
        assert enab is not None
        # ~0.033 m³ (10s + 10s flow), outage was rejected
        assert round(enab["m3"], 2) == 0.03


@pytest.mark.asyncio
async def test_water_today_at_360x_integrates_normal_spacing(client, monkeypatch):
    monkeypatch.setattr("app.core.clock.utcnow", lambda: datetime(2026, 11, 24, 12, tzinfo=UTC))
    clock.reset_to_real()
    clock.set_speed(360.0)
    now = clock.farm_now()
    async with async_session_factory() as db:
        # At 360x, throttling yields ~1 sample per real second = 360 farm-seconds.
        # Two consecutive samples 360 s apart: 6 m³/h for 360 s = 0.6 m³.
        # Plus an outage of 2000 farm seconds (> 1080 s limit) which must NOT be integrated.
        for offset in [-2720, -2360, -360, 0]:
            db.add(
                TelemetryPoint(
                    metric_key="zone.flow_m3h",
                    farm_id="farm_algaroshy",
                    zone_id="zone_rumman_1",
                    ts=now + timedelta(seconds=offset),
                    value_numeric=6.0,
                    value_text="360.0",
                )
            )
        await db.commit()

        zones = await telem_svc.water_today(db)
        rumman = next((z for z in zones if z["zone_id"] == "zone_rumman_1"), None)
        assert rumman is not None
        # Two 360s intervals = 0.6 + 0.6 = 1.2 m³. The 2000s gap (-2360 to -360) is NOT integrated!
        assert round(rumman["m3"], 1) == 1.2
    clock.reset_to_real()
