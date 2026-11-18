"""Command endpoints — /api/v1/commands."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, get_actor, require_service, require_user
from app.models.command import Command
from app.schemas.command import (
    CommandCreate,
    CommandRejection,
    CommandResponse,
    CommandSyncUpdate,
)
from app.services import commands as svc

router = APIRouter(prefix="/commands", tags=["Commands"])


@router.post(
    "",
    response_model=CommandResponse,
    status_code=201,
    responses={409: {"model": CommandRejection, "description": "Blocked by an interlock"}},
)
async def dispatch_command(
    req: CommandCreate,
    actor: Actor = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate a command, run interlocks, and queue it for the simulator/PLC."""
    try:
        cmd = await svc.submit_command(db, req, actor)
    except svc.CommandRejected as exc:
        return JSONResponse(
            status_code=409,
            content=CommandRejection(
                code=exc.code, message=exc.message, command_id=exc.command_id
            ).model_dump(),
        )
    return CommandResponse.model_validate(cmd)


@router.get("", response_model=list[CommandResponse])
async def list_commands(
    limit: int = Query(20, ge=1, le=200),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Most recent commands first."""
    result = await db.execute(select(Command).order_by(Command.requested_at.desc()).limit(limit))
    return [CommandResponse.model_validate(c) for c in result.scalars()]


@router.get("/pending", response_model=list[CommandResponse])
async def get_pending_commands(
    _: Actor = Depends(require_service), db: AsyncSession = Depends(get_db)
):
    """Simulator/PLC bridge polls for commands to execute."""
    await svc.expire_stale_commands(db)
    result = await db.execute(
        select(Command).where(Command.status == "pending").order_by(Command.requested_at)
    )
    return [CommandResponse.model_validate(c) for c in result.scalars()]


@router.patch("/{command_id}/sync", response_model=CommandResponse)
async def sync_command_status(
    command_id: str,
    update: CommandSyncUpdate,
    _: Actor = Depends(require_service),
    db: AsyncSession = Depends(get_db),
):
    """Simulator/PLC bridge reports command progress."""
    return CommandResponse.model_validate(await svc.sync_command(db, command_id, update))
