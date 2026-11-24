"""Backups — /api/v1/backups (Milestone G7). Owner/admin only."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import Actor, require_admin
from app.services import backup
from app.services.events import log_event

router = APIRouter(prefix="/backups", tags=["Backups"])


@router.get("")
async def backups_status(_: Actor = Depends(require_admin)):
    return backup.status()


@router.post("")
async def backup_now(actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if backup.db_path() is None:
        raise HTTPException(status_code=409, detail="Backups need the SQLite database")
    result = await backup.make_backup("manual")
    await log_event(
        db,
        "backup_created",
        "system",
        result["name"],
        actor_type="user",
        actor_id=actor.actor_id,
        payload={"usb": result["usb"], "drive": result["drive"]},
    )
    await db.commit()
    return result


@router.post("/{name}/restore")
async def restore_on_restart(
    name: str, actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    try:
        backup.request_restore(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Backup not found") from None
    await log_event(
        db, "restore_requested", "system", name, actor_type="user", actor_id=actor.actor_id
    )
    await db.commit()
    return {"pending_restore": name}


@router.delete("/restore")
async def cancel_restore(actor: Actor = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    name = backup.pending_restore()
    backup.cancel_restore()
    if name:
        await log_event(
            db, "restore_cancelled", "system", name, actor_type="user", actor_id=actor.actor_id
        )
        await db.commit()
    return {"pending_restore": None}
