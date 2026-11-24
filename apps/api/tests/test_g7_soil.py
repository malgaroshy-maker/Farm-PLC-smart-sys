"""G7 soil: crop levels, probes and the gateway ingest, soil logic, extra-run approval."""

import asyncio
import json
from datetime import timedelta

from conftest import SIM, login, push_state

from app.core.clock import clock
from app.database import async_session_factory
from app.services import soil


def confirm(client, admin, crop="grapes", start=45.0, stop=85.0):
    r = client.put(
        f"/api/v1/soil/levels/{crop}",
        headers=admin,
        json={"start_pct": start, "stop_pct": stop, "confirmed": True},
    )
    assert r.status_code == 200, r.text


def test_relative_conversion():
    assert soil.relative(7.0) == 0.0 and soil.relative(18.0) == 100.0
    assert soil.relative(12.5) == 50.0
    assert soil.relative(30.0) == 120.0  # clamped, over-watering stays visible


def test_levels_start_unconfirmed_and_validate(client):
    admin, op = login(client, "admin"), login(client, "operator")
    rows = {r["crop_type"]: r for r in client.get("/api/v1/soil/levels", headers=op).json()}
    assert rows["olives"]["start_pct"] == 40 and rows["olives"]["confirmed"] is False
    bad = client.put(
        "/api/v1/soil/levels/olives",
        headers=admin,
        json={"start_pct": 80, "stop_pct": 40, "confirmed": True},
    )
    assert bad.status_code == 422
    assert (
        client.put(
            "/api/v1/soil/levels/olives",
            headers=op,
            json={"start_pct": 40, "stop_pct": 85, "confirmed": True},
        ).status_code
        == 403
    )


def test_probe_registration_and_ingest_override_map_moisture(client):
    admin, op = login(client, "admin"), login(client, "operator")
    push_state(client)
    r = client.post(
        "/api/v1/soil/probes",
        headers=admin,
        json={"external_id": "a840414bc1d2e3f4", "zone_id": "zone_enab", "depth_cm": 30},
    )
    assert r.status_code == 201, r.text
    assert (
        client.post(
            "/api/v1/soil/probes",
            headers=admin,
            json={"external_id": "A840414BC1D2E3F4", "zone_id": "zone_enab", "depth_cm": 30},
        ).status_code
        == 409
    )
    r = client.post(
        "/api/v1/ingest/soil", headers=SIM, json={"device_id": "A840414BC1D2E3F4", "vwc_pct": 12.5}
    )
    assert r.status_code == 200 and r.json()["moisture_pct"] == 50.0
    assert (
        client.post(
            "/api/v1/ingest/soil", headers=op, json={"device_id": "x", "vwc_pct": 1}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/ingest/soil", headers=SIM, json={"device_id": "nope", "vwc_pct": 1}
        ).status_code
        == 404
    )
    state = client.get("/api/v1/state/map", headers=op).json()
    z = next(z for z in state["zones"] if z["zone_id"] == "zone_enab")
    assert z["moisture_pct"] == 50.0  # probe wins over the controller's 40 %


def test_dry_zone_raises_alarm_and_suggests_an_extra_run_that_starts_it(client):
    admin, op = login(client, "admin"), login(client, "operator")
    confirm(client, admin, "grapes", 45, 85)
    push_state(client, zone_extra={"zone_enab": {"moisture_pct": 20.0}})
    codes = {
        (a["alarm_code"], a.get("zone_id")) for a in client.get("/api/v1/alarms", headers=op).json()
    }
    assert ("ALM-017", "zone_enab") in codes

    async def run_soil_logic():
        from app.services.live_state import load_snapshots
        from app.services.scheduler import scheduler

        async with async_session_factory() as db:
            await scheduler._soil_logic(db, await load_snapshots(db))
            await db.commit()

    asyncio.run(run_soil_logic())
    sugs = [
        s
        for s in client.get("/api/v1/ai/suggestions", headers=op).json()
        if s.get("zone_id") == "zone_enab"
    ]
    assert sugs and sugs[0]["action_payload"]["action"] == "extra_run"
    r = client.post(f"/api/v1/ai/suggestions/{sugs[0]['id']}/approve", headers=op)
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "extra_run" and r.json()["command_id"]


def test_unconfirmed_levels_do_nothing(client):
    op = login(client, "operator")
    push_state(client, zone_extra={"zone_enab": {"moisture_pct": 5.0}})
    codes = {a["alarm_code"] for a in client.get("/api/v1/alarms", headers=op).json()}
    assert "ALM-017" not in codes


def test_full_zone_is_skipped_by_the_scheduler(client):
    admin = login(client, "admin")
    confirm(client, admin, "grapes", 45, 85)
    push_state(client, zone_extra={"zone_enab": {"moisture_pct": 95.0}})
    start = (clock.farm_now() + timedelta(minutes=1)).strftime("%H:%M")
    prog = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Soil test",
            "start_time_local": start,
            "weekday_mask": "1,2,3,4,5,6,7",
            "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 10}],
        },
    )
    assert prog.status_code == 201, prog.text

    async def fire():
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.program import Program
        from app.services.scheduler import scheduler

        async with async_session_factory() as db:
            p = (
                await db.execute(
                    select(Program)
                    .options(selectinload(Program.steps))
                    .where(Program.id == prog.json()["id"])
                )
            ).scalar_one()
            await scheduler._execute_program_step(db, p, 0, {"program_id": p.id})
            await db.commit()

    asyncio.run(fire())
    events = client.get("/api/v1/events", params={"limit": 50}, headers=admin).json()
    assert any(
        e["event_type"] == "schedule.skipped" and "soil_full" in json.dumps(e.get("payload"))
        for e in events
    )
    client.delete(f"/api/v1/schedules/{prog.json()['id']}", headers=admin)


def test_running_zone_stops_early_when_soil_is_full(client):
    admin = login(client, "admin")
    confirm(client, admin, "grapes", 45, 85)
    push_state(
        client,
        zone_states={"zone_enab": "running"},
        zone_extra={"zone_enab": {"moisture_pct": 92.0}},
    )

    async def run_soil_logic():
        from app.services.live_state import load_snapshots
        from app.services.scheduler import scheduler

        async with async_session_factory() as db:
            await scheduler._soil_logic(db, await load_snapshots(db))
            await db.commit()

    asyncio.run(run_soil_logic())
    cmds = client.get("/api/v1/commands", headers=admin).json()
    rows = cmds["items"] if isinstance(cmds, dict) else cmds
    assert any(c["command_type"] == "stop_zone" and c["target_id"] == "zone_enab" for c in rows)
