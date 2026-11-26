"""Durable pump history from fresh controller feedback."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc, utcnow
from app.models.pump import Pump, PumpObservationSpan
from app.schemas.state import StateSyncPayload


def pump_history_source() -> str:
    if settings.deployment_mode == "simulation" or settings.controller_mode == "simulator":
        return "simulation"
    return "controller"


async def record_pump_feedback(db: AsyncSession, payloads: list[StateSyncPayload]) -> None:
    wall_now = utcnow()
    samples: dict[str, tuple[datetime, bool | None]] = {}
    for payload in payloads:
        if not payload.device_key.startswith("pump_"):
            continue
        pump_id = payload.state_json.get("pump_id")
        if not isinstance(pump_id, str) or payload.device_key != f"pump_{pump_id}":
            continue
        feedback = payload.state_json.get("run_fb")
        if not isinstance(feedback, bool) or payload.state_json.get("run_fb_observed") is False:
            feedback = None
        sampled_at = as_utc(payload.updated_at)
        age = (wall_now - sampled_at).total_seconds()
        if 0 <= age <= settings.state_stale_after_sec and (
            pump_id not in samples or sampled_at > samples[pump_id][0]
        ):
            samples[pump_id] = (sampled_at, feedback)
    if not samples:
        return

    # Sync's snapshot writes acquire SQLite's writer lock before history is read.
    await db.flush()
    known = await db.scalars(
        select(Pump.id).where(Pump.id.in_(samples)).order_by(Pump.id).with_for_update()
    )
    source = pump_history_source()
    simulated_clock = not clock.is_locked_real and clock.mode == "sim"
    timeline = clock.updated_at.isoformat() if simulated_clock else "real"
    for pump_id in known:
        sampled_at, running = samples[pump_id]
        at = clock.farm_now(sampled_at)
        previous = await db.scalar(
            select(PumpObservationSpan)
            .where(PumpObservationSpan.pump_id == pump_id)
            .order_by(PumpObservationSpan.id.desc())
            .limit(1)
        )
        continuous = False
        if previous:
            seconds = (sampled_at - as_utc(previous.last_sample_at)).total_seconds()
            if seconds <= 0:
                continue
            if running is None and previous.running is None:
                previous.last_sample_at = sampled_at
                continue
            continuous = (
                seconds <= settings.state_stale_after_sec
                and previous.source == source
                and previous.timeline == timeline
                and at >= as_utc(previous.observed_until)
                and previous.running is not None
                and running is not None
            )
        if continuous and previous:
            previous.observed_until = at
            previous.last_sample_at = sampled_at
            if previous.running == running:
                continue

        db.add(
            PumpObservationSpan(
                pump_id=pump_id,
                source=source,
                timeline=timeline,
                running=running,
                start_observed=bool(continuous and previous and not previous.running and running),
                observed_from=at,
                observed_until=at,
                last_sample_at=sampled_at,
            )
        )


async def summarize_pump_history(
    db: AsyncSession, pump_id: str, start: datetime, stop: datetime, source: str
) -> dict:
    window_seconds = max(0.0, (stop - start).total_seconds())
    spans = await db.scalars(
        select(PumpObservationSpan)
        .where(
            PumpObservationSpan.pump_id == pump_id,
            PumpObservationSpan.source == source,
            PumpObservationSpan.observed_from < stop,
            PumpObservationSpan.observed_until >= start,
        )
        .order_by(PumpObservationSpan.observed_from, PumpObservationSpan.id)
    )
    covered = runtime = 0.0
    starts: set[datetime] = set()
    cursor = start
    overlaps = False
    for span in spans:
        began = as_utc(span.observed_from)
        interval_start = max(start, began)
        end = min(stop, as_utc(span.observed_until))
        if interval_start < cursor and end > interval_start:
            overlaps = True
        if span.start_observed and began >= cursor:
            starts.add(began)
        seconds = max(0.0, (end - max(cursor, interval_start)).total_seconds())
        covered += seconds
        if span.running:
            runtime += seconds
        if seconds:
            cursor = end
    status = "unavailable"
    if covered or starts:
        status = "complete" if covered >= window_seconds and not overlaps else "partial"
    return {
        "runtime_hours": round(runtime / 3600, 4) if covered else None,
        "start_count": len(starts) if covered or starts else None,
        "observed_seconds": round(covered, 3),
        "window_seconds": round(window_seconds, 3),
        "history_status": status,
        "history_source": source,
    }
