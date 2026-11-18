"""
Command service — the single path for anything that changes equipment state.

Order of checks:
  1. permission (role)            → 403, not persisted
  2. structure (target, payload)  → 404 / 422, not persisted
  3. interlocks (live state)      → 409, persisted as `rejected` for the audit trail
  4. accepted                     → persisted as `pending` for the simulator/PLC to pick up

The PLC remains the final safety authority; these checks stop obviously unsafe
requests early and give the operator a clear reason.
"""

import json
from datetime import timedelta
from itertools import combinations
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.domain import (
    ACTIVE_ZONE_STATES,
    COMMAND_PERMISSIONS,
    NOT_IMPLEMENTED_COMMANDS,
    SYSTEM_MODES,
    TERMINAL_COMMAND_STATUSES,
)
from app.core.timeutil import as_utc, utcnow
from app.deps import Actor
from app.models.command import Command
from app.models.pump import Pump
from app.models.zone import Zone, ZoneCombination
from app.schemas.command import CommandCreate, CommandResponse, CommandSyncUpdate
from app.services.events import log_event
from app.services.live_state import Snapshot, is_fresh, load_snapshots
from app.services.realtime import manager

FAULT_TARGETS = {"pump", "valve", "system"}


class CommandRejected(Exception):
    def __init__(self, code: str, message: str, command_id: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.command_id = command_id


class _Interlock(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ── Validation ───────────────────────────────────────────


def _check_permission(req: CommandCreate, actor: Actor) -> None:
    if req.command_type in NOT_IMPLEMENTED_COMMANDS:
        raise HTTPException(422, f"Command '{req.command_type}' is not implemented yet")
    allowed = COMMAND_PERMISSIONS.get(req.command_type, frozenset())
    if actor.role not in allowed:
        raise HTTPException(403, f"Role '{actor.role}' may not issue '{req.command_type}'")


async def _validate_structure(db: AsyncSession, req: CommandCreate) -> Zone | None:
    ct, payload = req.command_type, req.payload or {}
    if ct in ("start_zone", "stop_zone"):
        if req.target_type != "zone" or not req.target_id:
            raise HTTPException(422, f"'{ct}' requires target_type 'zone' and a target_id")
        zone = await db.get(Zone, req.target_id)
        if not zone:
            raise HTTPException(404, f"Zone '{req.target_id}' not found")
        return zone
    if ct in ("stop_all", "set_mode"):
        if req.target_type != "system" or req.target_id:
            raise HTTPException(422, f"'{ct}' requires target_type 'system' and no target_id")
        if ct == "set_mode" and payload.get("mode") not in SYSTEM_MODES:
            raise HTTPException(422, f"payload.mode must be one of {list(SYSTEM_MODES)}")
        return None
    if ct == "inject_fault":
        if settings.deployment_mode != "simulation":
            raise HTTPException(422, "Fault injection is only available in simulation mode")
        if req.target_type != "simulator":
            raise HTTPException(422, "'inject_fault' requires target_type 'simulator'")
        if payload.get("target_type") not in FAULT_TARGETS or not payload.get("fault_type"):
            raise HTTPException(422, "payload needs target_type (pump|valve|system) and fault_type")
        return None
    raise HTTPException(422, f"Unsupported command '{ct}'")


async def _open_commands(db: AsyncSession, command_type: str) -> list[Command]:
    result = await db.execute(
        select(Command).where(
            Command.command_type == command_type,
            Command.status.not_in(TERMINAL_COMMAND_STATUSES),
        )
    )
    return list(result.scalars())


async def _check_start_interlocks(
    db: AsyncSession, zone: Zone, snapshots: dict[str, Snapshot]
) -> None:
    """Interlocks from PLC_CONTROL_LOGIC.md §5 that the backend can evaluate today."""
    if not zone.enabled:
        raise _Interlock("zone_disabled", f"Zone {zone.code} is disabled")
    if not is_fresh(snapshots):
        raise _Interlock(
            "state_stale", "Live state is stale — cannot verify interlocks (is the simulator up?)"
        )

    mode = snapshots.get("system_mode")
    mode_value = mode.state.get("mode") if mode else "off"
    if mode_value not in ("auto", "manual"):
        raise _Interlock("mode_blocks_start", f"System mode '{mode_value}' does not allow starts")

    zone_states = {
        s.state.get("zone_id"): s.state.get("state")
        for k, s in snapshots.items()
        if k.startswith("zone_")
    }
    if zone_states.get(zone.id) in ACTIVE_ZONE_STATES:
        raise _Interlock("zone_already_active", f"Zone {zone.code} is already running")

    pending_starts = {c.target_id for c in await _open_commands(db, "start_zone")}
    if zone.id in pending_starts:
        raise _Interlock("duplicate_command", f"A start for zone {zone.code} is already pending")

    active = {zid for zid, st in zone_states.items() if st in ACTIVE_ZONE_STATES} | pending_starts
    if len(active) >= settings.max_concurrent_zones:
        raise _Interlock(
            "max_concurrent_zones",
            f"Max {settings.max_concurrent_zones} zone(s) may run at once; active: "
            + ", ".join(sorted(active)),
        )
    if active:
        group = sorted(active | {zone.id})
        for a, b in combinations(group, 2):
            combo = (
                await db.execute(
                    select(ZoneCombination).where(
                        or_(
                            and_(ZoneCombination.zone_a_id == a, ZoneCombination.zone_b_id == b),
                            and_(ZoneCombination.zone_a_id == b, ZoneCombination.zone_b_id == a),
                        )
                    )
                )
            ).scalar_one_or_none()
            if not combo or not combo.allowed:
                raise _Interlock(
                    "combination_not_allowed", f"Zones {a} and {b} may not run together"
                )

    pumps = (await db.execute(select(Pump).where(Pump.enabled.is_(True)))).scalars().all()
    pump_live = {
        s.state.get("pump_id"): s.state for k, s in snapshots.items() if k.startswith("pump_")
    }
    if not any(not pump_live.get(p.id, {}).get("fault", False) for p in pumps):
        raise _Interlock("no_pump_available", "No healthy, enabled pump is available")

    stats = snapshots.get("simulation_stats")
    tank = stats.state.get("tank_level_pct", 0.0) if stats else 0.0
    if tank < settings.tank_critical_pct and not zone.allows_direct_well:
        raise _Interlock(
            "tank_critically_low",
            f"Tank at {tank:.1f}% (< {settings.tank_critical_pct:.0f}%) and zone "
            f"{zone.code} cannot use the direct well",
        )


# ── Public API ───────────────────────────────────────────


async def submit_command(db: AsyncSession, req: CommandCreate, actor: Actor) -> Command:
    _check_permission(req, actor)
    zone = await _validate_structure(db, req)

    cmd = Command(
        id=uuid4().hex,
        command_type=req.command_type,
        target_type=req.target_type,
        target_id=req.target_id,
        payload_json=json.dumps(req.payload) if req.payload else None,
        requested_by=actor.actor_id,
        actor_type=actor.actor_type,
        status="pending",
        requested_at=utcnow(),
    )
    rejection: _Interlock | None = None
    if req.command_type == "start_zone" and zone is not None:
        try:
            await _check_start_interlocks(db, zone, await load_snapshots(db))
        except _Interlock as exc:
            rejection = exc
            cmd.status = "rejected"
            cmd.failure_reason = f"{exc.code}: {exc.message}"
            cmd.completed_at = cmd.requested_at

    db.add(cmd)
    await log_event(
        db,
        "command.rejected" if rejection else "command.requested",
        req.target_type,
        req.target_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        payload={
            "command_id": cmd.id,
            "command_type": cmd.command_type,
            **({"reason": cmd.failure_reason} if rejection else {}),
        },
    )
    await db.commit()
    await manager.broadcast("command.updated", CommandResponse.model_validate(cmd))
    if rejection:
        raise CommandRejected(rejection.code, rejection.message, cmd.id)
    return cmd


async def sync_command(db: AsyncSession, command_id: str, update: CommandSyncUpdate) -> Command:
    cmd = await db.get(Command, command_id)
    if not cmd:
        raise HTTPException(404, "Command not found")
    if cmd.status in TERMINAL_COMMAND_STATUSES:
        raise HTTPException(409, f"Command already {cmd.status}")
    cmd.status = update.status
    now = utcnow()
    cmd.acknowledged_at = update.acknowledged_at or cmd.acknowledged_at or now
    if update.status in TERMINAL_COMMAND_STATUSES:
        cmd.completed_at = update.completed_at or now
    if update.failure_reason:
        cmd.failure_reason = update.failure_reason
    await log_event(
        db,
        f"command.{update.status}",
        cmd.target_type,
        cmd.target_id,
        actor_type="plc",
        payload={"command_id": cmd.id, "reason": update.failure_reason},
    )
    await db.commit()
    await manager.broadcast("command.updated", CommandResponse.model_validate(cmd))
    return cmd


async def expire_stale_commands(db: AsyncSession) -> list[Command]:
    """Mark commands nobody picked up in time as timed_out."""
    cutoff = utcnow() - timedelta(seconds=settings.command_timeout_sec)
    result = await db.execute(
        select(Command).where(Command.status.not_in(TERMINAL_COMMAND_STATUSES))
    )
    expired = [c for c in result.scalars() if as_utc(c.requested_at) < cutoff]
    for c in expired:
        c.status = "timed_out"
        c.completed_at = utcnow()
        c.failure_reason = f"No response from controller within {settings.command_timeout_sec:.0f}s"
        await log_event(
            db,
            "command.timed_out",
            c.target_type,
            c.target_id,
            actor_type="system",
            payload={"command_id": c.id},
        )
    if expired:
        await db.commit()
        for c in expired:
            await manager.broadcast("command.updated", CommandResponse.model_validate(c))
    return expired
