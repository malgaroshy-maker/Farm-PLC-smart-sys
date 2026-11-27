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

import asyncio
import json
from datetime import datetime
from itertools import combinations
from uuid import uuid4
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
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

FAULT_TARGETS = {"pump", "valve", "zone", "system", "sensor", "tank", "comms"}


class CommandRejected(Exception):
    def __init__(self, code: str, message: str, command_id: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.command_id = command_id


class ProgramStopped(Exception):
    """STOP ALL was pressed after this program run began, so its next step must not start."""


class _Interlock(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ── Validation ───────────────────────────────────────────


async def _check_permission(db: AsyncSession, req: CommandCreate, actor: Actor) -> None:
    if req.command_type in NOT_IMPLEMENTED_COMMANDS:
        raise HTTPException(422, f"Command '{req.command_type}' is not implemented yet")
    allowed = COMMAND_PERMISSIONS.get(req.command_type, frozenset())
    if actor.role not in allowed:
        from app.services.alarms import engine as alarm_engine  # avoid import cycle

        await alarm_engine.raise_event(
            db,
            "ALM-035",
            detail=f"{actor.name or actor.actor_id} ({actor.role}) tried {req.command_type}",
            zone_id=req.target_id if req.target_type == "zone" else None,
        )
        raise HTTPException(403, f"Role '{actor.role}' may not issue '{req.command_type}'")


async def _validate_structure(db: AsyncSession, req: CommandCreate) -> Zone | None:
    ct, payload = req.command_type, req.payload or {}
    if ct in ("start_zone", "stop_zone"):
        if req.target_type != "zone" or not req.target_id:
            raise HTTPException(422, f"'{ct}' requires target_type 'zone' and a target_id")
        zone = await db.get(Zone, req.target_id)
        if not zone:
            raise HTTPException(404, f"Zone '{req.target_id}' not found")
        duration = payload.get("duration_min")
        if ct == "start_zone" and duration is not None:
            if not isinstance(duration, int) or not 1 <= duration <= zone.max_runtime_min:
                raise HTTPException(
                    422, f"payload.duration_min must be 1–{zone.max_runtime_min} minutes"
                )
        if ct == "start_zone" and duration is None:
            # always send an explicit duration: the PLC refuses an open-ended start (G5)
            req.payload = {**payload, "duration_min": zone.default_duration_min}
        return zone
    if ct in ("stop_all", "set_mode", "reset_alarm"):
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
            raise HTTPException(
                422, f"payload needs target_type ({'|'.join(sorted(FAULT_TARGETS))}) and fault_type"
            )
        return None
    if ct == "set_panel":
        if settings.deployment_mode != "simulation":
            raise HTTPException(422, "Panel switches are set by hand on the real panel")
        if req.target_type != "simulator" or not req.target_id:
            raise HTTPException(422, "'set_panel' requires target_type 'simulator' and a target_id")
        kind, pos = payload.get("kind"), payload.get("position")
        valid = {"zone": ("auto", "on", "off"), "pump": ("auto", "hand", "off")}
        if kind not in valid or pos not in valid[kind]:
            raise HTTPException(422, "payload needs kind (zone|pump) and a valid position")
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
    from app.services.alarms import blocking_critical, open_alarms  # avoid import cycle

    critical = blocking_critical(await open_alarms(db))
    if critical:
        raise _Interlock(
            "critical_alarm_active",
            f"Critical alarm {critical.alarm_code} must be cleared and reset first",
        )
    if not is_fresh(snapshots, controller_only=True):
        raise _Interlock(
            "state_stale", "Live state is stale — cannot verify interlocks (is the simulator up?)"
        )

    mode = snapshots.get("system_mode")
    mode_value = mode.state.get("mode") if mode else "off"
    if mode_value not in ("auto", "manual"):
        raise _Interlock("mode_blocks_start", f"System mode '{mode_value}' does not allow starts")
    if mode and mode.state.get("power_ok") is False:
        raise _Interlock("no_power", "Mains power is off at the farm")
    panel = (
        snapshots.get(f"zone_{zone.id}").state.get("panel_mode", "auto")
        if snapshots.get(f"zone_{zone.id}")
        else "auto"
    )
    if panel != "auto":
        raise _Interlock(
            "zone_manual", f"Zone {zone.code} is switched to {panel.upper()} on the panel"
        )

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

    def usable(p) -> bool:
        live = pump_live.get(p.id, {})
        return not live.get("fault", False) and live.get("panel_mode", "auto") != "off"

    if not any(usable(p) for p in pumps):
        raise _Interlock("no_pump_available", "No healthy, enabled pump is available")

    stats = snapshots.get("simulation_stats")
    tank = stats.state.get("tank_level_pct", 0.0) if stats else 0.0
    if tank < settings.tank_critical_pct and not zone.allows_direct_well:
        raise _Interlock(
            "tank_critically_low",
            f"Tank at {tank:.1f}% (< {settings.tank_critical_pct:.0f}%) and zone "
            f"{zone.code} cannot use the direct well",
        )


STOPS = ("stop_zone", "stop_all")


async def _supersede_starts(db: AsyncSession, req: CommandCreate) -> list[Command]:
    """A stop cancels any open start for the same zone(s).

    Without this a start the controller never finished (e.g. it restarted
    mid-sequence) would count as an active zone until the execution timeout.
    """
    open_starts = await _open_commands(db, "start_zone")
    hit = [c for c in open_starts if req.command_type == "stop_all" or c.target_id == req.target_id]
    now = clock.farm_now()
    for c in hit:
        c.status = "failed"
        c.completed_at = now
        c.failure_reason = f"Superseded by {req.command_type}"
        from app.services.cycles import record_cycle_aborted_by_command

        await record_cycle_aborted_by_command(db, c.id, c.failure_reason)
        await log_event(
            db,
            "command.failed",
            c.target_type,
            c.target_id,
            actor_type="system",
            payload={"command_id": c.id, "reason": c.failure_reason},
        )
    return hit


# ── Public API ───────────────────────────────────────────

# Interlocks read what is already open, then save the new command. Starts and stops take turns
# so two starts cannot both pass, and a stop cannot miss a start that is being saved.
# One lock per event loop; this covers the single API process the app runs as.
_submit_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


def command_turn() -> asyncio.Lock:
    return _submit_locks.setdefault(asyncio.get_running_loop(), asyncio.Lock())


async def stopped_all_since(db: AsyncSession, since: datetime) -> bool:
    found = await db.scalar(
        select(Command.id)
        .where(Command.command_type == "stop_all", Command.requested_at_real >= as_utc(since))
        .limit(1)
    )
    return found is not None


async def submit_command(
    db: AsyncSession,
    req: CommandCreate,
    actor: Actor,
    *,
    program_run_since: datetime | None = None,
) -> Command:
    await _check_permission(db, req, actor)
    zone = await _validate_structure(db, req)
    # release any SQLite write lock the caller holds before waiting for our turn
    await db.commit()
    async with command_turn():
        if program_run_since and await stopped_all_since(db, program_run_since):
            raise ProgramStopped
        return await _check_and_save(db, req, actor, zone)


async def _check_and_save(
    db: AsyncSession, req: CommandCreate, actor: Actor, zone: Zone | None
) -> Command:
    cmd = Command(
        id=uuid4().hex,
        command_type=req.command_type,
        target_type=req.target_type,
        target_id=req.target_id,
        payload_json=json.dumps(req.payload) if req.payload else None,
        requested_by=actor.actor_id,
        actor_type=actor.actor_type,
        status="pending",
        requested_at=clock.farm_now(),
        requested_at_real=utcnow(),
    )
    rejection: _Interlock | None = None
    if req.command_type == "stop_zone" and zone is not None:
        snap = (await load_snapshots(db)).get(f"zone_{zone.id}")
        if snap and snap.state.get("panel_mode") == "on":
            rejection = _Interlock(
                "zone_manual",
                f"Zone {zone.code} is switched ON on the panel; turn the switch to stop it",
            )
            cmd.status = "rejected"
            cmd.failure_reason = f"{rejection.code}: {rejection.message}"
            cmd.completed_at = cmd.requested_at
    if req.command_type == "start_zone" and zone is not None:
        try:
            await _check_start_interlocks(db, zone, await load_snapshots(db))
        except _Interlock as exc:
            rejection = exc
            cmd.status = "rejected"
            cmd.failure_reason = f"{exc.code}: {exc.message}"
            cmd.completed_at = cmd.requested_at

    db.add(cmd)
    if req.command_type == "start_zone" and not rejection and zone is not None:
        from app.services.cycles import record_cycle_start

        await record_cycle_start(db, cmd, zone, actor, req.payload)

    superseded = await _supersede_starts(db, req) if req.command_type in STOPS else []
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
    for c in (*superseded, cmd):
        await manager.broadcast("command.updated", CommandResponse.model_validate(c))
    if rejection:
        raise CommandRejected(rejection.code, rejection.message, cmd.id)
    return cmd


async def record_controller_stop_all(db: AsyncSession) -> list[Command]:
    """Stop all pressed on the PLC's own HMI: record it as a STOP ALL that is already done.

    From here it works like the app's own: it ends the running program and cancels starts the
    controller has not finished, so none of them can restart a zone. The caller holds
    command_turn() and commits. Returns the commands to broadcast.
    """
    cmd = Command(
        id=uuid4().hex,
        command_type="stop_all",
        target_type="system",
        actor_type="plc",
        status="completed",
        requested_at=clock.farm_now(),
        requested_at_real=utcnow(),
    )
    cmd.acknowledged_at = cmd.completed_at = cmd.requested_at
    superseded = await _supersede_starts(
        db, CommandCreate(command_type="stop_all", target_type="system")
    )
    db.add(cmd)
    await log_event(
        db,
        "command.completed",
        "system",
        None,
        actor_type="plc",
        payload={"command_id": cmd.id, "command_type": "stop_all", "source": "hmi"},
    )
    return [*superseded, cmd]


async def sync_command(db: AsyncSession, command_id: str, update: CommandSyncUpdate) -> Command:
    cmd = await db.get(Command, command_id)
    if not cmd:
        raise HTTPException(404, "Command not found")
    if cmd.status in TERMINAL_COMMAND_STATUSES:
        raise HTTPException(409, f"Command already {cmd.status}")
    cmd.status = update.status
    now = clock.farm_now()
    req_at = as_utc(cmd.requested_at) if cmd.requested_at else now
    now = max(now, req_at)
    if cmd.acknowledged_at is None:
        cmd.acknowledged_at = now
    if update.status in TERMINAL_COMMAND_STATUSES:
        ack_at = as_utc(cmd.acknowledged_at) if cmd.acknowledged_at else now
        cmd.completed_at = max(now, ack_at)
    if update.failure_reason:
        cmd.failure_reason = update.failure_reason
    if update.status in ("failed", "rejected"):
        from app.services.cycles import record_cycle_aborted_by_command

        await record_cycle_aborted_by_command(
            db, cmd.id, update.failure_reason or cmd.failure_reason
        )
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
    """Time out commands nobody picked up (short) or that never finished (long)."""
    now_real = utcnow()
    now_farm = clock.farm_now()
    result = await db.execute(
        select(Command).where(Command.status.not_in(TERMINAL_COMMAND_STATUSES))
    )
    expired = []
    for c in result.scalars():
        limit = (
            settings.command_timeout_sec
            if c.status == "pending"
            else settings.command_execution_timeout_sec
        )
        ref_real = as_utc(c.requested_at_real or c.requested_at)
        if (now_real - ref_real).total_seconds() > limit:
            expired.append((c, limit))
    for c, limit in expired:
        c.status = "timed_out"
        c.completed_at = now_farm
        c.failure_reason = f"No response from controller within {limit:.0f}s"
        if c.command_type == "start_zone":
            from app.services.cycles import record_cycle_aborted_by_command

            await record_cycle_aborted_by_command(db, c.id, c.failure_reason)
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
        for c, _ in expired:
            await manager.broadcast("command.updated", CommandResponse.model_validate(c))
    return [c for c, _ in expired]
