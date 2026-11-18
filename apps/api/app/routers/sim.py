"""Simulation control — /api/v1/sim (admin only, simulation mode only)."""

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.deps import Actor, get_actor, require_admin
from app.services.scenarios import runner

router = APIRouter(prefix="/sim", tags=["Simulation"])


def _simulation_only() -> None:
    if settings.deployment_mode != "simulation":
        raise HTTPException(404, "Simulation controls are disabled outside simulation mode")


@router.get("/scenarios", dependencies=[Depends(_simulation_only)])
async def list_scenarios(_: Actor = Depends(get_actor)):
    return {"scenarios": runner.catalog(), "run": runner.state.as_dict()}


@router.post("/scenarios/{name}/run", dependencies=[Depends(_simulation_only)])
async def run_scenario(name: str, _: Actor = Depends(require_admin)):
    return runner.start(name).as_dict()


@router.post("/scenarios/stop", dependencies=[Depends(_simulation_only)])
async def stop_scenario(_: Actor = Depends(require_admin)):
    return (await runner.stop()).as_dict()
