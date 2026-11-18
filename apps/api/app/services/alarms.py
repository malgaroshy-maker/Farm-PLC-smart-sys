"""
Alarm engine — owns the alarm lifecycle (ALARM_MATRIX.md §5, §11).

Inputs
  * PLC conditions: the simulator/PLC reports what it currently sees in the
    `plc_alarms` snapshot (it has already acted: stopped zones, isolated pumps).
  * Derived conditions: rules the backend evaluates from live state
    (tank warning, pressure warnings, modes, stale data, repeated faults).
  * Events: one-shot alarms such as an unauthorized command attempt.

Lifecycle per alarm instance (one open instance per correlation key):
  condition true  → active_unacked ──ack──▶ active_acked
  condition false → cleared_at set; the alarm stays *latched* while it still
                    needs an ack (requires_ack) or a reset (requires_manual_reset);
                    otherwise it becomes `cleared` (history).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.alarm_catalog import CATALOG, SEVERITY_RANK, AlarmSpec
from app.core.timeutil import as_utc, utcnow
from app.deps import Actor
from app.models.alarm import Alarm
from app.models.command import Command
from app.models.event_log import EventLog
from app.models.zone import Zone
from app.schemas.alarm import AlarmResponse
from app.services.events import log_event
from app.services.live_state import Snapshot, last_update
from app.services.realtime import manager

OPEN = ("active_unacked", "active_acked")
MAINTENANCE_DONE = "zone.maintenance_done"


@dataclass
class Condition:
    code: str
    zone_id: str | None = None
    device_id: str | None = None
    value: float | None = None
    threshold: float | None = None
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.code}:{self.zone_id or self.device_id or 'system'}"


def resolve_status(alarm: Alarm, spec: AlarmSpec) -> str:
    if alarm.cleared_at is None:
        return "active_acked" if alarm.acknowledged_at else "active_unacked"
    if spec.requires_ack and not alarm.acknowledged_at:
        return "active_unacked"
    if spec.requires_manual_reset and not alarm.reset_at:
        return "active_acked"
    return "cleared"


def to_response(a: Alarm) -> AlarmResponse:
    spec = CATALOG.get(a.alarm_code)
    return AlarmResponse(
        id=a.id,
        alarm_code=a.alarm_code,
        name=spec.name if spec else a.alarm_code,
        name_ar=spec.name_ar if spec else None,
        severity=a.severity,
        category=a.category,
        status=a.status,
        zone_id=a.zone_id,
        device_type=a.device_type,
        device_id=a.device_id,
        source_layer=a.source_layer,
        current_value=a.current_value,
        threshold_value=a.threshold_value,
        triggered_at=a.triggered_at,
        acknowledged_at=a.acknowledged_at,
        acknowledged_by=a.acknowledged_by,
        cleared_at=a.cleared_at,
        reset_at=a.reset_at,
        reset_by=a.reset_by,
        message_en=a.message_en,
        message_ar=a.message_ar,
        guidance_en=a.guidance_en,
        guidance_ar=a.guidance_ar,
        condition_active=a.cleared_at is None,
        requires_ack=spec.requires_ack if spec else False,
        requires_manual_reset=spec.requires_manual_reset if spec else False,
    )


async def open_alarms(db: AsyncSession) -> list[Alarm]:
    result = await db.execute(
        select(Alarm).where(Alarm.status.in_(OPEN)).order_by(Alarm.triggered_at.desc())
    )
    return list(result.scalars())


async def active_alarm_responses(db: AsyncSession) -> list[AlarmResponse]:
    alarms = await open_alarms(db)
    alarms.sort(
        key=lambda a: (-SEVERITY_RANK.get(a.severity, 0), -as_utc(a.triggered_at).timestamp())
    )
    return [to_response(a) for a in alarms]


def _device_type(device_id: str | None) -> str | None:
    if not device_id:
        return None
    return device_id.split("_", 1)[0]  # pump_… / valve_… / sensor_…


class AlarmEngine:
    def __init__(self) -> None:
        self._pending_since: dict[str, datetime] = {}

    # ── Condition evaluation ─────────────────────────────

    @staticmethod
    def plc_conditions(snapshots: dict[str, Snapshot]) -> list[Condition]:
        snap = snapshots.get("plc_alarms")
        if not snap:
            return []
        out = []
        for raw in snap.state.get("active", []):
            if raw.get("code") in CATALOG:
                out.append(
                    Condition(
                        code=raw["code"],
                        zone_id=raw.get("zone_id"),
                        device_id=raw.get("device_id"),
                        value=raw.get("value"),
                        threshold=raw.get("threshold"),
                        detail=raw.get("detail") or "",
                    )
                )
        return out

    def _debounced(self, key: str, active: bool, seconds: float, now: datetime) -> bool:
        if not active:
            self._pending_since.pop(key, None)
            return False
        since = self._pending_since.setdefault(key, now)
        return (now - since).total_seconds() >= seconds

    async def derived_conditions(
        self, db: AsyncSession, snapshots: dict[str, Snapshot], now: datetime
    ) -> list[Condition]:
        out: list[Condition] = []
        stats = snapshots.get("simulation_stats")
        mode = snapshots.get("system_mode")
        if stats:
            tank = float(stats.state.get("tank_level_pct", 100.0))
            low = settings.tank_critical_pct <= tank < settings.tank_warning_pct
            if self._debounced("ALM-001", low, settings.tank_warning_debounce_sec, now):
                out.append(
                    Condition("ALM-001", value=round(tank, 1), threshold=settings.tank_warning_pct)
                )

            running = [
                s.state.get("zone_id")
                for k, s in snapshots.items()
                if k.startswith("zone_")
                and s.state.get("state") == "running"
                and s.state.get("source_mode") != "well_direct"
            ]
            if running:
                zones = (await db.execute(select(Zone).where(Zone.id.in_(running)))).scalars().all()
                p = float(stats.state.get("main_pressure_bar", 0.0))
                p_min = max((z.pressure_min_bar for z in zones), default=0.0)
                p_max = min((z.pressure_max_bar for z in zones), default=99.0)
                if self._debounced("ALM-008", p < p_min, settings.alarm_debounce_sec, now):
                    out.append(Condition("ALM-008", value=round(p, 2), threshold=p_min))
                if self._debounced("ALM-010", p > p_max, settings.alarm_debounce_sec, now):
                    out.append(Condition("ALM-010", value=round(p, 2), threshold=p_max))
            else:
                self._debounced("ALM-008", False, 0, now)
                self._debounced("ALM-010", False, 0, now)
        if mode:
            m = mode.state.get("mode")
            if m == "manual":
                out.append(Condition("ALM-042"))
            elif m == "maintenance":
                out.append(Condition("ALM-043"))

        # ALM-036: repeated major faults on the same zone in 24 h. A recorded
        # "maintenance done" restarts that zone's window, so the alarm clears
        # as soon as the repair is signed off.
        since = now - timedelta(hours=24)
        done_at = {
            zid: as_utc(at)
            for zid, at in (
                await db.execute(
                    select(EventLog.entity_id, func.max(EventLog.occurred_at))
                    .where(EventLog.event_type == MAINTENANCE_DONE, EventLog.occurred_at >= since)
                    .group_by(EventLog.entity_id)
                )
            ).all()
        }

        def after_cutoff(zone_id: str | None, at: datetime) -> bool:
            cut = done_at.get(zone_id or "")
            return cut is None or as_utc(at) > cut

        counts: dict[str, int] = {}
        for zone_id, at in await db.execute(
            select(Alarm.zone_id, Alarm.triggered_at).where(
                Alarm.zone_id.is_not(None),
                Alarm.triggered_at >= since,
                Alarm.severity.in_(("S2", "S3")),
                Alarm.alarm_code != "ALM-036",
            )
        ):
            if after_cutoff(zone_id, at):
                counts[zone_id] = counts.get(zone_id, 0) + 1
        # A persistent fault (e.g. a valve that stays stuck) keeps ONE alarm open
        # across retries, so also count starts the controller aborted.
        failed: dict[str, int] = {}
        for zone_id, at in await db.execute(
            select(Command.target_id, Command.requested_at).where(
                Command.command_type == "start_zone",
                Command.status == "failed",
                Command.requested_at >= since,
                Command.failure_reason.not_like("Superseded%"),
            )
        ):
            if after_cutoff(zone_id, at):
                failed[zone_id] = failed.get(zone_id, 0) + 1
        for zone_id, n in failed.items():
            counts[zone_id] = max(counts.get(zone_id, 0), n)
        for zone_id, count in counts.items():
            if zone_id and count >= settings.repeated_fault_threshold:
                out.append(Condition("ALM-036", zone_id=zone_id, value=float(count)))
        return out

    @staticmethod
    def staleness_conditions(snapshots: dict[str, Snapshot], now: datetime) -> list[Condition]:
        last = last_update(snapshots)
        if last is None:
            return []
        age = (now - last).total_seconds()
        out = []
        if age > settings.state_stale_after_sec:
            out.append(
                Condition("ALM-044", value=round(age, 1), threshold=settings.state_stale_after_sec)
            )
        if age > settings.comm_lost_after_sec:
            out.append(
                Condition("ALM-029", value=round(age, 1), threshold=settings.comm_lost_after_sec)
            )
        return out

    # ── Reconciliation ───────────────────────────────────

    async def reconcile(
        self,
        db: AsyncSession,
        conditions: Iterable[Condition],
        scope_codes: set[str],
    ) -> list[tuple[str, Alarm]]:
        """Bring open alarms for `scope_codes` in line with the current conditions."""
        now = utcnow()
        wanted = {c.key: c for c in conditions if c.code in scope_codes}
        existing = {
            a.correlation_key: a
            for a in (
                await db.execute(
                    select(Alarm).where(
                        Alarm.status.in_(OPEN),
                        Alarm.alarm_code.in_(scope_codes),
                    )
                )
            ).scalars()
        }
        events: list[tuple[str, Alarm]] = []

        for key, cond in wanted.items():
            alarm = existing.get(key)
            if alarm is not None and alarm.cleared_at is None:
                alarm.current_value = cond.value  # still active: refresh value
                continue
            if alarm is not None:
                # condition came back while latched → re-arm the same instance
                alarm.cleared_at = None
                alarm.status = resolve_status(alarm, CATALOG[cond.code])
                events.append(("alarm.active", alarm))
                continue
            alarm = self._new_alarm(cond, now)
            db.add(alarm)
            events.append(("alarm.active", alarm))
            await log_event(
                db,
                "alarm.active",
                "alarm",
                alarm.id,
                actor_type=alarm.source_layer,
                payload={"code": cond.code, "zone_id": cond.zone_id, "device_id": cond.device_id},
            )

        for key, alarm in existing.items():
            if key in wanted or alarm.cleared_at is not None:
                continue
            alarm.cleared_at = now
            alarm.status = resolve_status(alarm, CATALOG[alarm.alarm_code])
            if alarm.status == "cleared":
                events.append(("alarm.cleared", alarm))
                await log_event(db, "alarm.cleared", "alarm", alarm.id, actor_type="system")
            else:
                events.append(("alarm.updated", alarm))
        return events

    @staticmethod
    def _new_alarm(cond: Condition, now: datetime) -> Alarm:
        spec = CATALOG[cond.code]
        detail = f" ({cond.detail})" if cond.detail else ""
        return Alarm(
            id=uuid4().hex,
            alarm_code=cond.code,
            severity=spec.severity,
            category=spec.category,
            status="active_unacked",
            zone_id=cond.zone_id,
            device_type=_device_type(cond.device_id),
            device_id=cond.device_id,
            source_layer=spec.source,
            current_value=cond.value,
            threshold_value=cond.threshold,
            triggered_at=now,
            message_en=spec.message_en + detail,
            message_ar=spec.message_ar,
            guidance_en=spec.guidance_en,
            guidance_ar=spec.guidance_ar,
            correlation_key=cond.key,
        )

    # ── Entry points ─────────────────────────────────────

    async def on_state_sync(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> None:
        now = utcnow()
        plc_codes = {c for c, s in CATALOG.items() if s.source == "plc"}
        derived_codes = {"ALM-001", "ALM-008", "ALM-010", "ALM-036", "ALM-042", "ALM-043"}
        events = await self.reconcile(db, self.plc_conditions(snapshots), plc_codes)
        events += await self.reconcile(
            db, await self.derived_conditions(db, snapshots, now), derived_codes
        )
        # fresh data just arrived → staleness alarms clear
        events += await self.reconcile(db, [], {"ALM-029", "ALM-044"})
        await self._publish(db, events)

    async def on_monitor_tick(self, db: AsyncSession, snapshots: dict[str, Snapshot]) -> None:
        events = await self.reconcile(
            db, self.staleness_conditions(snapshots, utcnow()), {"ALM-029", "ALM-044"}
        )
        await self._publish(db, events)

    async def raise_event(
        self,
        db: AsyncSession,
        code: str,
        *,
        value: float | None = None,
        detail: str = "",
        zone_id: str | None = None,
        device_id: str | None = None,
    ) -> Alarm:
        """One-shot alarm (condition is momentary) — e.g. ALM-035."""
        now = utcnow()
        cond = Condition(code, zone_id=zone_id, device_id=device_id, value=value, detail=detail)
        alarm = self._new_alarm(cond, now)
        alarm.correlation_key = f"{cond.key}:{alarm.id[:8]}"
        alarm.cleared_at = now
        alarm.status = resolve_status(alarm, CATALOG[code])
        db.add(alarm)
        await log_event(
            db,
            "alarm.active",
            "alarm",
            alarm.id,
            actor_type="system",
            payload={"code": code, "detail": detail},
        )
        await self._publish(db, [("alarm.active", alarm)])
        return alarm

    async def _publish(self, db: AsyncSession, events: list[tuple[str, Alarm]]) -> None:
        if not events:
            return
        await db.commit()
        for event_type, alarm in events:
            await manager.broadcast(event_type, to_response(alarm))

    # ── Operator actions ─────────────────────────────────

    async def acknowledge(self, db: AsyncSession, alarm_id: str, actor: Actor) -> Alarm:
        alarm = await db.get(Alarm, alarm_id)
        if not alarm:
            raise HTTPException(404, "Alarm not found")
        if alarm.status != "active_unacked":
            raise HTTPException(409, f"Alarm is {alarm.status}; nothing to acknowledge")
        alarm.acknowledged_at = utcnow()
        alarm.acknowledged_by = actor.actor_id
        alarm.status = resolve_status(alarm, CATALOG[alarm.alarm_code])
        await log_event(
            db,
            "alarm.acknowledged",
            "alarm",
            alarm.id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        await self._publish(db, [("alarm.acknowledged", alarm)])
        return alarm

    async def reset(self, db: AsyncSession, alarm_id: str, actor: Actor) -> Alarm:
        alarm = await db.get(Alarm, alarm_id)
        if not alarm:
            raise HTTPException(404, "Alarm not found")
        if alarm.status == "cleared":
            raise HTTPException(409, "Alarm is already cleared")
        if alarm.cleared_at is None:
            raise HTTPException(409, "Condition is still active — fix the cause before resetting")
        if not alarm.acknowledged_at:
            alarm.acknowledged_at = utcnow()
            alarm.acknowledged_by = actor.actor_id
        alarm.reset_at = utcnow()
        alarm.reset_by = actor.actor_id
        alarm.status = "cleared"
        await log_event(
            db,
            "alarm.reset",
            "alarm",
            alarm.id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        await self._publish(db, [("alarm.reset", alarm)])
        return alarm

    async def reset_all_cleared(self, db: AsyncSession, actor: Actor) -> int:
        """Reset every latched alarm whose condition is gone (scenario prep)."""
        latched = [a for a in await open_alarms(db) if a.cleared_at is not None]
        for a in latched:
            a.acknowledged_at = a.acknowledged_at or utcnow()
            a.reset_at, a.reset_by, a.status = utcnow(), actor.actor_id, "cleared"
        await self._publish(db, [("alarm.reset", a) for a in latched])
        return len(latched)


def blocking_critical(alarms: Iterable[Alarm]) -> Alarm | None:
    """First open S3 alarm that must block new zone starts (tank handled separately)."""
    for a in alarms:
        if a.severity == "S3" and a.alarm_code != "ALM-002":
            return a
    return None


engine = AlarmEngine()


def summary(alarms: list[Any]) -> dict[str, int]:
    out = {"S0": 0, "S1": 0, "S2": 0, "S3": 0}
    for a in alarms:
        out[a.severity] = out.get(a.severity, 0) + 1
    return out
