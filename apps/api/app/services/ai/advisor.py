"""Weather Advisor Workflow & Approval Service (Milestone E).

Implements:
  - Deterministic threshold checks (rain > 50% or precip > 2mm -> skip; heat/ET0 -> extend)
  - LLM bilingual explanation generation
  - Suggestions lifecycle (pending, approved, rejected)
  - Approving generates a one-day ProgramOverride for the scheduler
"""

import json
import logging
from datetime import date, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc
from app.models.ai import AISuggestion, ProgramOverride
from app.models.program import Program
from app.services.ai.advisor_rules import AdviceInputs, decide, explain
from app.services.ai.agent import run_weather_advisor
from app.services.conflicts import parse_weekday_mask
from app.services.events import log_event
from app.services.live_state import current_map_state
from app.services.realtime import manager
from app.services.weather import is_usable_forecast, weather_service

log = logging.getLogger(__name__)


async def evaluate_weather_advisor(
    db: AsyncSession,
    target_date: str | None = None,
    force_refresh: bool = False,
    refresh_weather: bool = False,
    lang: str = "ar",
) -> AISuggestion | None:
    """Evaluate weather thresholds and create an approval-ready AISuggestion."""
    now_farm = clock.farm_now()
    date_str = (
        target_date or now_farm.astimezone(ZoneInfo(settings.farm_timezone)).date().isoformat()
    )

    forecast = await weather_service.get_forecast(db=db, force_refresh=refresh_weather)
    if not forecast or not forecast.daily or not is_usable_forecast(forecast):
        log.info("No weather forecast available for advisor")
        return None

    # Check if target_date exists in forecast
    day_summary = None
    for d in forecast.daily:
        if d.date == date_str:
            day_summary = d
            break
    if not day_summary:
        return None

    # Programs that run on the target day -> the zones the advice affects
    weekday = date.fromisoformat(date_str).isoweekday()
    prog_res = await db.execute(
        select(Program)
        .where(Program.enabled.is_(True))
        .options(selectinload(Program.steps))
        .order_by(Program.start_time_local, Program.id)
    )
    programs = [
        p for p in prog_res.scalars().all() if weekday in parse_weekday_mask(p.weekday_mask)
    ]
    program = next((p for p in programs if p.steps), None)
    if program is None:
        return None
    affected_zones = sorted({step.zone_id for step in program.steps})

    # Only observations for the selected program inform its decision.
    state = await current_map_state(db)
    zm = [
        z.moisture_pct
        for z in state.zones
        if z.moisture_pct is not None and z.zone_id in affected_zones and state.data_fresh
    ]
    decision = decide(
        AdviceInputs(
            rain_mm=day_summary.precipitation_total_mm,
            rain_pct=day_summary.precipitation_probability_pct,
            temp_max_c=day_summary.temp_max_c,
            et0_mm=day_summary.et0_mm,
            moisture_avg_pct=(sum(zm) / len(zm)) if zm else None,
            moisture_min_pct=min(zm) if zm else None,
            zones_count=len(affected_zones),
        )
    )
    if decision.action == "none":
        log.info(
            "Conditions normal on %s (%s); no advisor suggestion needed", date_str, decision.rule
        )
        return None

    # Check if pending suggestion already exists for this date to avoid duplicates
    if not force_refresh:
        stmt = (
            select(AISuggestion)
            .where(
                AISuggestion.feature == "weather_advisor",
                AISuggestion.status == "pending",
            )
            .order_by(desc(AISuggestion.created_at))
        )
        res = await db.execute(stmt)
        existing = res.scalars().all()
        for s in existing:
            if s.action_payload_json:
                try:
                    p = json.loads(s.action_payload_json)
                    if (
                        p.get("scope_version") == 1
                        and p.get("target_date") == date_str
                        and p.get("program_id") == program.id
                    ):
                        return s
                except Exception:
                    pass

    # Generate bilingual explanation via LLM agent (or rule-based fallback)
    suggestion_model = await run_weather_advisor(
        forecast=forecast,
        target_date=date_str,
        affected_zones=affected_zones,
        program_id=program.id,
        db=db,
        lang=lang,
        decision=decision,
    )
    if (
        suggestion_model.provider_used == "rule_based"
        or suggestion_model.action != decision.action
        or suggestion_model.duration_factor != decision.duration_factor
        or suggestion_model.target_date != date_str
        or suggestion_model.program_id != program.id
        or set(suggestion_model.affected_zone_ids) != set(affected_zones)
    ):
        (
            suggestion_model.title,
            suggestion_model.title_ar,
            suggestion_model.reasoning,
            suggestion_model.reasoning_ar,
        ) = explain(decision)
        suggestion_model.provider_used = "rule_based"
        suggestion_model.model_used = "offline_rules"

    action_payload = {
        "action": decision.action,
        "target_date": date_str,
        "duration_factor": decision.duration_factor,
        "affected_zone_ids": affected_zones,
        "program_id": program.id,
        "scope_version": 1,
        "provider_used": suggestion_model.provider_used,
        "model_used": suggestion_model.model_used,
        # "why?" details (Milestone G2)
        "rule": decision.rule,
        "inputs": decision.inputs,
        "weather_summary": {
            "condition": day_summary.condition,
            "temperature_c": day_summary.temp_max_c,
            "rain_probability_pct": day_summary.precipitation_probability_pct,
            "precipitation_mm": day_summary.precipitation_total_mm,
            "et0_mm": day_summary.et0_mm,
        },
    }

    suggestion = AISuggestion(
        id=f"sug_{uuid4().hex[:12]}",
        feature="weather_advisor",
        priority="high" if decision.action == "skip" else "medium",
        status="pending",
        title=suggestion_model.title,
        title_ar=suggestion_model.title_ar,
        description=suggestion_model.reasoning,
        description_ar=suggestion_model.reasoning_ar,
        reasoning=suggestion_model.reasoning,
        reasoning_ar=suggestion_model.reasoning_ar,
        action_payload_json=json.dumps(action_payload),
        confidence=suggestion_model.confidence,
        created_at=now_farm,
        expires_at=now_farm + timedelta(days=2),
    )

    db.add(suggestion)
    await db.commit()
    await db.refresh(suggestion)

    await log_event(
        db,
        "ai.suggestion.new",
        "ai_suggestion",
        suggestion.id,
        actor_type="ai",
        payload={
            "feature": "weather_advisor",
            "action": decision.action,
            "target_date": date_str,
            "title": suggestion.title,
        },
    )
    await manager.broadcast(
        "ai.suggestion.new",
        {
            "id": suggestion.id,
            "feature": "weather_advisor",
            "action": decision.action,
            "target_date": date_str,
            "title": suggestion.title,
            "title_ar": suggestion.title_ar,
            "status": "pending",
        },
    )

    return suggestion


async def approve_suggestion(
    db: AsyncSession,
    suggestion_id: str,
    operator_name: str = "operator",
) -> ProgramOverride:
    """Approve an advisor suggestion and create a one-day ProgramOverride."""
    suggestion = await db.get(AISuggestion, suggestion_id)
    if not suggestion:
        raise ValueError(f"Suggestion '{suggestion_id}' not found")
    if suggestion.status != "pending":
        raise ValueError(f"Suggestion '{suggestion_id}' is already {suggestion.status}")

    now_farm = clock.farm_now()
    payload = json.loads(suggestion.action_payload_json or "{}")

    if suggestion.expires_at and as_utc(suggestion.expires_at) <= as_utc(now_farm):
        raise ValueError("Suggestion has expired. Generate a new suggestion.")
    if suggestion.feature != "weather_advisor" or payload.get("scope_version") != 1:
        raise ValueError("Suggestion lacks a verified program scope. Generate a new suggestion.")
    target_date = payload.get("target_date")
    action = payload.get("action")
    factor = payload.get("duration_factor")
    program_id = payload.get("program_id")
    program = await db.get(Program, program_id) if program_id else None
    try:
        target_day = date.fromisoformat(target_date or "")
    except ValueError as exc:
        raise ValueError("Suggestion has an invalid target date.") from exc
    if (
        not program
        or not program.enabled
        or target_day < now_farm.astimezone(ZoneInfo(settings.farm_timezone)).date()
        or target_day.isoweekday() not in parse_weekday_mask(program.weekday_mask)
        or sorted({step.zone_id for step in program.steps}) != payload.get("affected_zone_ids")
        or action not in ("skip", "extend", "reduce")
        or not isinstance(factor, (float, int))
        or not (
            (action == "skip" and factor == 0)
            or (action == "extend" and 1 < factor <= 1.3)
            or (action == "reduce" and 0 < factor < 1)
        )
    ):
        raise ValueError(
            "Suggestion no longer matches an eligible program. Generate a new suggestion."
        )

    claim = await db.execute(
        update(AISuggestion)
        .where(AISuggestion.id == suggestion_id, AISuggestion.status == "pending")
        .values(status="approved", responded_at=now_farm, responded_by=operator_name)
    )
    if claim.rowcount != 1:
        raise ValueError("Suggestion is no longer pending.")

    override = ProgramOverride(
        id=f"ovr_{uuid4().hex[:12]}",
        program_id=program_id,
        target_date=target_date,
        action=action,
        duration_factor=factor,
        applied=False,
        suggestion_id=suggestion.id,
        created_at=now_farm,
    )
    db.add(override)

    await db.commit()
    await db.refresh(override)

    await log_event(
        db,
        "ai.suggestion.approved",
        "ai_suggestion",
        suggestion.id,
        actor_type="user",
        actor_id=operator_name,
        payload={
            "override_id": override.id,
            "action": action,
            "target_date": target_date,
            "duration_factor": factor,
        },
    )
    await manager.broadcast(
        "ai.suggestion.approved",
        {
            "suggestion_id": suggestion.id,
            "override_id": override.id,
            "action": action,
            "target_date": target_date,
        },
    )

    return override


async def expire_suggestions(db: AsyncSession) -> int:
    """Pending suggestions past their time stop being offered."""
    now = as_utc(clock.farm_now())
    rows = await db.scalars(select(AISuggestion).where(AISuggestion.status == "pending"))
    old = [s for s in rows if s.expires_at and as_utc(s.expires_at) <= now]
    for s in old:
        s.status = "expired"
    return len(old)


async def undo_approval(db: AsyncSession, suggestion_id: str, operator_name: str) -> None:
    """Take back an approved one-day change that no run has used yet."""
    suggestion = await db.get(AISuggestion, suggestion_id)
    if not suggestion or suggestion.status != "approved":
        raise ValueError("Only an approved suggestion can be undone.")
    overrides = list(
        await db.scalars(
            select(ProgramOverride).where(ProgramOverride.suggestion_id == suggestion_id)
        )
    )
    if not overrides or any(o.applied for o in overrides):
        raise ValueError("This change was already used and cannot be undone.")
    for override in overrides:
        await db.delete(override)
    suggestion.status, suggestion.responded_at, suggestion.responded_by = "pending", None, None
    await db.commit()
    await log_event(
        db,
        "ai.suggestion.undone",
        "ai_suggestion",
        suggestion_id,
        actor_type="user",
        actor_id=operator_name,
    )
    await manager.broadcast(
        "ai.suggestion.undone", {"suggestion_id": suggestion_id, "status": "pending"}
    )


async def reject_suggestion(
    db: AsyncSession,
    suggestion_id: str,
    operator_name: str = "operator",
) -> AISuggestion:
    """Reject an advisor suggestion."""
    suggestion = await db.get(AISuggestion, suggestion_id)
    if not suggestion:
        raise ValueError(f"Suggestion '{suggestion_id}' not found")
    if suggestion.status != "pending":
        raise ValueError(f"Suggestion '{suggestion_id}' is already {suggestion.status}")

    now_farm = clock.farm_now()
    suggestion.status = "rejected"
    suggestion.responded_at = now_farm
    suggestion.responded_by = operator_name

    await db.commit()
    await db.refresh(suggestion)

    await log_event(
        db,
        "ai.suggestion.rejected",
        "ai_suggestion",
        suggestion.id,
        actor_type="user",
        actor_id=operator_name,
    )
    await manager.broadcast(
        "ai.suggestion.rejected",
        {
            "suggestion_id": suggestion.id,
            "status": "rejected",
        },
    )

    return suggestion
