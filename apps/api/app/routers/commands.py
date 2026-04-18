"""Command endpoints — Dispatch and Sync /api/v1/commands."""

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.command import Command
from app.schemas.command import CommandCreate, CommandResponse, CommandSyncUpdate

router = APIRouter(prefix="/commands", tags=["Commands"])


@router.post("", response_model=CommandResponse)
async def dispatch_command(cmd_req: CommandCreate, db: AsyncSession = Depends(get_db)):
    """Dispatch a new command to the simulator/PLC."""
    cmd = Command(
        id=uuid4().hex,
        command_type=cmd_req.command_type,
        target_type=cmd_req.target_type,
        target_id=cmd_req.target_id,
        payload_json=json.dumps(cmd_req.payload) if cmd_req.payload else None,
        status="pending",
        requested_at=datetime.utcnow()
    )
    db.add(cmd)
    await db.flush()
    await db.refresh(cmd)
    
    return CommandResponse.model_validate(cmd)


@router.get("/pending", response_model=list[CommandResponse])
async def get_pending_commands(db: AsyncSession = Depends(get_db)):
    """Simulator polls for pending commands to execute."""
    result = await db.execute(
        select(Command)
        .where(Command.status == "pending")
        .order_by(Command.requested_at)
    )
    return result.scalars().all()


@router.patch("/{command_id}/sync", response_model=CommandResponse)
async def sync_command_status(
    command_id: str, 
    update: CommandSyncUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Simulator updates the status of an executing command."""
    cmd = await db.get(Command, command_id)
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")
        
    cmd.status = update.status
    if update.acknowledged_at:
        cmd.acknowledged_at = update.acknowledged_at
    if update.completed_at:
        cmd.completed_at = update.completed_at
    if update.failure_reason:
        cmd.failure_reason = update.failure_reason
        
    await db.flush()
    await db.refresh(cmd)
    return CommandResponse.model_validate(cmd)
