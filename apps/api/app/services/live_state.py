"""
Live device state cache.

The simulator (later: the PLC bridge) pushes snapshots keyed by device_key:
  system_mode, simulation_stats, zone_<id>, pump_<id>, valve_<id>, sensor_<id>
This module reads them back as one FarmMapState and computes change events.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.models.telemetry import DeviceStateSnapshot
from app.schemas.state import FarmMapState, StateSyncPayload


@dataclass
class Snapshot:
    state: dict[str, Any]
    updated_at: datetime


async def load_snapshots(db: AsyncSession) -> dict[str, Snapshot]:
    rows = (await db.execute(select(DeviceStateSnapshot))).scalars().all()
    return {r.device_key: Snapshot(json.loads(r.state_json), as_utc(r.updated_at)) for r in rows}


def last_update(
    snapshots: dict[str, Snapshot], *, controller_only: bool = False
) -> datetime | None:
    return max(
        (
            snapshot.updated_at
            for key, snapshot in snapshots.items()
            if not controller_only
            or key in ("system_mode", "simulation_stats", "plc_alarms")
            or key.startswith(("zone_", "pump_", "valve_"))
        ),
        default=None,
    )


def is_fresh(
    snapshots: dict[str, Snapshot], now: datetime | None = None, *, controller_only: bool = False
) -> bool:
    last = last_update(snapshots, controller_only=controller_only)
    if last is None:
        return False
    return 0 <= ((now or utcnow()) - last).total_seconds() <= settings.state_stale_after_sec


def build_map_state(
    snapshots: dict[str, Snapshot], active_alarms: list[Any] | None = None
) -> FarmMapState:
    zones, pumps, valves, sensors = [], [], [], []
    system_mode = "off"
    power_ok, fallback_active = True, False
    stats: dict[str, Any] = {}
    for key, snap in sorted(snapshots.items()):
        if key == "system_mode":
            system_mode = snap.state.get("mode", "off")
            power_ok = bool(snap.state.get("power_ok", True))
            fallback_active = bool(snap.state.get("fallback_active", False))
        elif key == "simulation_stats":
            stats = snap.state
        elif key.startswith("zone_"):
            zones.append(snap.state)
        elif key.startswith("pump_"):
            pumps.append(snap.state)
        elif key.startswith("valve_"):
            valves.append(snap.state)
        elif key.startswith("sensor_"):
            sensors.append(snap.state)
        # plc_alarms is consumed by the alarm engine, not shown raw

    # G7: fresh soil probes (posted by the gateway) override the controller's moisture value
    from app.services.soil import probe_readings

    probes = probe_readings(snapshots)
    if probes:
        zones = [
            {
                **z,
                "moisture_pct": round(
                    sum(float(p["value"]) for p in probes[z["zone_id"]])
                    / len(probes[z["zone_id"]]),
                    1,
                ),
            }
            if z.get("zone_id") in probes
            else z
            for z in zones
        ]
    last = last_update(snapshots, controller_only=True)
    farm_clock = clock.as_dict()
    return FarmMapState(
        system_mode=system_mode,
        power_ok=power_ok,
        fallback_active=fallback_active,
        zones=zones,
        pumps=pumps,
        valves=valves,
        sensors=sensors,
        tank_level_pct=stats.get("tank_level_pct", 0.0),
        main_pressure_bar=stats.get("main_pressure_bar", 0.0),
        main_flow_m3h=stats.get("main_flow_m3h", 0.0),
        well_level_m=stats.get("well_level_m"),
        filter_dp_bar=stats.get("filter_dp_bar"),
        active_alarms=active_alarms or [],
        data_fresh=is_fresh(snapshots, controller_only=True),
        last_snapshot_ts=last,
        farm_now=farm_clock["farm_now"],
        speed=farm_clock["speed"],
        clock_mode=farm_clock["mode"],
        clock_paused=farm_clock["paused"],
        locked_real=farm_clock["locked_real"],
    )


async def upsert_snapshots(
    db: AsyncSession, payloads: list[StateSyncPayload]
) -> list[StateSyncPayload]:
    """Return newer or changed snapshots that were accepted, one per device."""
    newest: dict[str, StateSyncPayload] = {}
    for payload in payloads:
        previous = newest.get(payload.device_key)
        if previous is None or as_utc(payload.updated_at) >= as_utc(previous.updated_at):
            newest[payload.device_key] = payload
    if not newest:
        return []

    # A stored time ahead of our own clock means a clock was set back (e.g. a time sync on the
    # gateway or this PC). Newer-only would then ignore every update until time caught up.
    future = utcnow() + timedelta(seconds=settings.state_stale_after_sec)
    records = [
        {
            "device_key": key,
            "state_json": json.dumps(newest[key].state_json, default=str, sort_keys=True),
            "updated_at": as_utc(newest[key].updated_at),
        }
        for key in sorted(newest)
    ]
    insert = {"sqlite": sqlite_insert, "postgresql": postgres_insert}.get(
        db.get_bind().dialect.name
    )
    if insert is not None:
        statement = insert(DeviceStateSnapshot).values(records)
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=[DeviceStateSnapshot.device_key],
            set_={"state_json": excluded.state_json, "updated_at": excluded.updated_at},
            where=or_(
                DeviceStateSnapshot.updated_at > future,
                DeviceStateSnapshot.updated_at < excluded.updated_at,
                and_(
                    DeviceStateSnapshot.updated_at == excluded.updated_at,
                    DeviceStateSnapshot.state_json != excluded.state_json,
                ),
            ),
        ).returning(DeviceStateSnapshot.device_key)
        accepted = set(await db.scalars(statement))
        return [payload for key, payload in newest.items() if key in accepted]

    rows = {
        r.device_key: r
        for r in (
            await db.execute(
                select(DeviceStateSnapshot).where(DeviceStateSnapshot.device_key.in_(newest))
            )
        ).scalars()
    }
    accepted = []
    for fields in records:
        row = rows.get(fields["device_key"])
        if row is None:
            db.add(DeviceStateSnapshot(**fields))
        elif (
            as_utc(row.updated_at) > future
            or fields["updated_at"] > as_utc(row.updated_at)
            or (
                fields["updated_at"] == as_utc(row.updated_at)
                and fields["state_json"] != row.state_json
            )
        ):
            row.state_json = fields["state_json"]
            row.updated_at = fields["updated_at"]
        else:
            continue
        accepted.append(newest[fields["device_key"]])
    return accepted


def diff_events(
    before: dict[str, Snapshot], payloads: list[StateSyncPayload]
) -> list[tuple[str, dict[str, Any]]]:
    """Return (event_type, payload) for meaningful state transitions."""
    events: list[tuple[str, dict[str, Any]]] = []
    for p in payloads:
        prev = before.get(p.device_key)
        prev_state = prev.state if prev else {}
        new = p.state_json
        if p.device_key == "system_mode":
            if prev_state.get("mode") != new.get("mode"):
                events.append(
                    (
                        "system.mode.changed",
                        {"previous_mode": prev_state.get("mode"), "current_mode": new.get("mode")},
                    )
                )
        elif p.device_key.startswith("zone_"):
            if prev_state.get("state") != new.get("state"):
                events.append(
                    (
                        "zone.state.changed",
                        {
                            "zone_id": new.get("zone_id"),
                            "previous_state": prev_state.get("state"),
                            "current_state": new.get("state"),
                            "pressure_bar": new.get("pressure_bar"),
                            "flow_m3h": new.get("flow_m3h"),
                            "moisture_pct": new.get("moisture_pct"),
                            "health": new.get("health"),
                        },
                    )
                )
        elif p.device_key.startswith("pump_"):
            if prev_state.get("state") != new.get("state") or prev_state.get("fault") != new.get(
                "fault"
            ):
                events.append(
                    (
                        "pump.state.changed",
                        {
                            "pump_id": new.get("pump_id"),
                            "previous_state": prev_state.get("state"),
                            "current_state": new.get("state"),
                            "fault": new.get("fault"),
                        },
                    )
                )
    return events


async def current_map_state(db: AsyncSession) -> FarmMapState:
    from app.services.alarms import active_alarm_responses  # avoid import cycle

    return build_map_state(await load_snapshots(db), await active_alarm_responses(db))
