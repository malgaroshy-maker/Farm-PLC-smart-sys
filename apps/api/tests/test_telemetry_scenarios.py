import time

from conftest import login, push_state

from app.services.scenarios import SCENARIOS, runner


def test_sync_records_history_and_series_endpoint(client):
    viewer = login(client, "viewer")
    push_state(client, tank=70)
    push_state(client, tank=60)
    r = client.get(
        "/api/v1/telemetry/series?metric_key=tank_level_pct&minutes=10&points=10", headers=viewer
    )
    assert r.status_code == 200
    points = r.json()["points"]
    assert points and points[-1]["min"] == 60 and points[-1]["max"] == 70

    r = client.get(
        "/api/v1/telemetry/series?metric_key=zone.moisture_pct&zone_id=zone_enab", headers=viewer
    )
    assert r.json()["points"][-1]["value"] == 40.0


def test_series_validates_metric(client):
    viewer = login(client, "viewer")
    assert (
        client.get("/api/v1/telemetry/series?metric_key=bogus", headers=viewer).status_code == 422
    )
    assert (
        client.get("/api/v1/telemetry/series?metric_key=zone.flow_m3h", headers=viewer).status_code
        == 422
    )


def test_scenario_catalog(client):
    r = client.get("/api/v1/sim/scenarios", headers=login(client, "viewer"))
    names = {s["name"] for s in r.json()["scenarios"]}
    assert {"pump_trip_mid_cycle", "mainline_leak", "comms_loss", "reset_farm"} <= names
    assert r.json()["run"]["status"] == "idle"


def test_only_admin_runs_scenarios(client):
    assert (
        client.post(
            "/api/v1/sim/scenarios/reset_farm/run", headers=login(client, "operator")
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/sim/scenarios/nope/run", headers=login(client, "admin")).status_code
        == 404
    )


def test_scenario_steps_reference_real_devices():
    from app.seed import PUMPS, ZONES

    zones = {z["id"] for z in ZONES}
    valves = {f"valve_{z['code'].lower()}" for z in ZONES}
    pumps = {p["id"] for p in PUMPS}
    for s in SCENARIOS.values():
        for step in s.steps:
            if step[0] == "fault" and step[2]:
                assert step[2] in zones | valves | pumps, (s.name, step)
            if step[0] in ("cmd",) and step[2] == "zone":
                assert step[3] in zones, (s.name, step)
            if step[0] == "wait_zone":
                assert step[1] in zones, (s.name, step)


def test_scenario_without_simulator_fails_cleanly(client, monkeypatch):
    """No simulator is running, so the expected alarm never appears → status 'failed'."""
    import app.services.scenarios as sc

    real_sleep = sc.asyncio.sleep
    monkeypatch.setattr(sc.asyncio, "sleep", lambda s: real_sleep(min(s, 0.01)))
    monkeypatch.setattr(sc, "SCENARIOS", {**SCENARIOS})
    sc.SCENARIOS["quick"] = sc.Scenario(
        "quick", "q", "q", "", ["ALM-006"], [("wait_alarm", "ALM-006", 0.05)], prep=False
    )
    admin = login(client, "admin")
    assert client.post("/api/v1/sim/scenarios/quick/run", headers=admin).status_code == 200
    for _ in range(100):
        state = client.get("/api/v1/sim/scenarios", headers=admin).json()["run"]
        if state["status"] != "running":
            break
        time.sleep(0.05)
    assert state["status"] == "failed"
    assert "ALM-006" in state["message"]
    assert not runner.busy


def test_water_today_integrates_flow(client):
    import asyncio
    from datetime import timedelta

    from app.core.timeutil import utcnow
    from app.database import async_session_factory
    from app.models.telemetry import TelemetryPoint

    async def seed_points():
        now = utcnow()
        async with async_session_factory() as db:
            # 6 m³/h for 30 s → 0.05 m³; plus a 10-minute gap that must NOT count
            for offset, q in [(-700, 6.0), (-40, 6.0), (-10, 6.0)]:
                db.add(
                    TelemetryPoint(
                        metric_key="zone.flow_m3h",
                        farm_id="farm_algaroshy",
                        zone_id="zone_enab",
                        ts=now + timedelta(seconds=offset),
                        value_numeric=q,
                    )
                )
            await db.commit()

    asyncio.run(seed_points())
    body = client.get("/api/v1/telemetry/water-today", headers=login(client, "viewer")).json()
    enab = next(z for z in body["zones"] if z["zone_id"] == "zone_enab")
    assert enab["m3"] == 0.05
    assert body["total_m3"] >= 0.05


def test_scenario_cleanup_programs_on_pass_and_fail(client, monkeypatch):
    """Scenarios must clean up prog_scen_* programs, steps, and scheduler state on pass, fail, or stop."""
    import asyncio

    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.program import Program, ProgramStep, SchedulerState
    from app.services.scenarios import cleanup_scenario_programs

    async def _setup_and_verify():
        async with async_session_factory() as db:
            # Seed leftover prog_scen_* programs, steps, and state
            p1 = Program(
                id="prog_scen_temp_1",
                name="Scenario Program 1",
                start_time_local="07:00",
                weekday_mask="1,2,3,4,5,6,7",
                enabled=True,
            )
            s1 = ProgramStep(
                id="step_scen_1",
                program_id="prog_scen_temp_1",
                zone_id="zone_enab",
                step_order=1,
                duration_min=15,
            )
            st1 = SchedulerState(
                key="scheduler.last_fired_prog_scen_temp_1",
                value_text="2026-11-19",
            )
            db.add_all([p1, s1, st1])
            await db.commit()

            # Verify seeded
            progs = (
                (await db.execute(select(Program).where(Program.id.like("prog_scen_%"))))
                .scalars()
                .all()
            )
            assert len(progs) >= 1

            # Execute cleanup
            cleaned = await cleanup_scenario_programs(db)
            assert cleaned >= 1
            await db.commit()

            # Verify all prog_scen_* are gone
            progs_after = (
                (await db.execute(select(Program).where(Program.id.like("prog_scen_%"))))
                .scalars()
                .all()
            )
            assert len(progs_after) == 0

            steps_after = (
                (
                    await db.execute(
                        select(ProgramStep).where(ProgramStep.program_id.like("prog_scen_%"))
                    )
                )
                .scalars()
                .all()
            )
            assert len(steps_after) == 0

            states_after = (
                (
                    await db.execute(
                        select(SchedulerState).where(SchedulerState.key.like("%prog_scen_%"))
                    )
                )
                .scalars()
                .all()
            )
            assert len(states_after) == 0

    asyncio.run(_setup_and_verify())
