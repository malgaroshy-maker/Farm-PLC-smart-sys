"""Simulation control — /api/v1/sim (admin only, simulation mode only)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.database import get_db
from app.deps import Actor, get_actor, require_admin
from app.schemas.clock import ClockResponse, ClockUpdateRequest
from app.schemas.command import CommandCreate
from app.services.commands import _supersede_starts
from app.services.events import log_event
from app.services.realtime import manager
from app.services.scenarios import runner

router = APIRouter(prefix="/sim", tags=["Simulation"])


def _simulation_only() -> None:
    if settings.deployment_mode != "simulation":
        raise HTTPException(404, "Simulation controls are disabled outside simulation mode")


@router.get("/clock", response_model=ClockResponse)
async def get_clock(_: Actor = Depends(get_actor)):
    return ClockResponse(**clock.as_dict())


@router.post("/clock", response_model=ClockResponse, dependencies=[Depends(_simulation_only)])
async def update_clock(
    body: ClockUpdateRequest,
    actor: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if clock.is_locked_real:
        raise HTTPException(409, "Clock is locked to real time in PLC controller mode")

    if body.real is True:
        if not body.confirm:
            raise HTTPException(
                400,
                "Resetting to real time clears operating history. Pass confirm=true to proceed.",
            )
        from app.reset_demo import reset_history

        await reset_history()
        clock.reset_to_real()
        await clock.save(db)
        await log_event(
            db,
            "clock.reset_to_real",
            "system",
            "clock",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    elif body.speed is not None:
        old_speed = clock.speed
        clock.set_speed(body.speed)
        await clock.save(db)
        await log_event(
            db,
            "clock.speed_changed",
            "system",
            "clock",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            payload={"speed": body.speed, "previous_speed": old_speed},
        )
    elif body.pause is not None:
        if body.pause:
            clock.pause()
            await clock.save(db)
            await log_event(
                db,
                "clock.paused",
                "system",
                "clock",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        else:
            clock.resume()
            await clock.save(db)
            await log_event(
                db,
                "clock.resumed",
                "system",
                "clock",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                payload={"speed": clock.speed},
            )
    elif body.step_min is not None:
        clock.step(body.step_min)
        await clock.save(db)
        await log_event(
            db,
            "clock.stepped",
            "system",
            "clock",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            payload={"step_min": body.step_min, "farm_now": clock.farm_now().isoformat()},
        )
    elif body.jump_to is not None:
        await _supersede_starts(db, CommandCreate(command_type="stop_all", target_type="system"))
        try:
            prev_sim, next_sim = clock.jump_to(body.jump_to)
        except ValueError as err:
            raise HTTPException(422, str(err)) from err
        await clock.save(db)
        await log_event(
            db,
            "clock.jumped",
            "system",
            "clock",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            payload={
                "jump_to": body.jump_to,
                "from": prev_sim.isoformat(),
                "to": next_sim.isoformat(),
            },
        )
    else:
        raise HTTPException(422, "No valid clock action supplied in request body")

    res = ClockResponse(**clock.as_dict())
    await manager.broadcast("clock.changed", res)
    return res


@router.get("/scenarios", dependencies=[Depends(_simulation_only)])
async def list_scenarios(_: Actor = Depends(get_actor)):
    return {"scenarios": runner.catalog(), "run": runner.state.as_dict()}


@router.post("/scenarios/{name}/run", dependencies=[Depends(_simulation_only)])
async def run_scenario(name: str, _: Actor = Depends(require_admin)):
    return runner.start(name).as_dict()


@router.post("/scenarios/stop", dependencies=[Depends(_simulation_only)])
async def stop_scenario(_: Actor = Depends(require_admin)):
    return (await runner.stop()).as_dict()
