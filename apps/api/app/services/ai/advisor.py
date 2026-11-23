"""Weather Advisor Workflow & Approval Service (Milestone E).

Implements:
  - Deterministic threshold checks (rain > 50% or precip > 2mm -> skip; heat/ET0 -> extend)
  - LLM bilingual explanation generation
  - Suggestions lifecycle (pending, approved, rejected)
  - Approving generates a one-day ProgramOverride for the scheduler
"""

import json
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import clock
from app.models.ai import AISuggestion, ProgramOverride
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program
from app.services.ai.advisor_rules import AdviceInputs, decide
from app.services.ai.agent import run_weather_advisor
from app.services.events import log_event
from app.services.live_state import current_map_state
from app.services.realtime import manager
from app.services.weather import weather_service

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
    date_str = target_date or now_farm.strftime("%Y-%m-%d")

    forecast = await weather_service.get_forecast(db=db, force_refresh=refresh_weather)
    if not forecast or not forecast.daily:
        log.info("No weather forecast available for advisor")
        return None

    # Check if target_date exists in forecast
    day_summary = None
    for d in forecast.daily:
        if d.date == date_str:
            day_summary = d
            break
    if not day_summary:
        day_summary = forecast.daily[0]
        date_str = day_summary.date

    # Programs that run on the target day -> the zones the advice affects
    from datetime import date as _date

    from app.services.conflicts import parse_weekday_mask

    weekday = _date.fromisoformat(date_str).isoweekday()
    prog_res = await db.execute(
        select(Program).where(Program.enabled.is_(True)).options(selectinload(Program.steps))
    )
    programs = [
        p for p in prog_res.scalars().all() if weekday in parse_weekday_mask(p.weekday_mask)
    ]
    affected_zones = sorted({s.zone_id for p in programs for s in (p.steps or [])})
    first_prog_id = programs[0].id if programs else None

    # Live soil moisture of those zones (all zones when none are scheduled)
    state = await current_map_state(db)
    zm = [
        z.moisture_pct
        for z in state.zones
        if z.moisture_pct is not None and (not affected_zones or z.zone_id in affected_zones)
    ]
    # Water delivered in the last 48 h of farm time
    water_48h = (
        await db.execute(
            select(func.coalesce(func.sum(IrrigationCycle.water_estimate_m3), 0.0)).where(
                IrrigationCycle.actual_end_at >= now_farm - timedelta(hours=48)
            )
        )
    ).scalar()

    decision = decide(
        AdviceInputs(
            rain_mm=day_summary.precipitation_total_mm,
            rain_pct=day_summary.precipitation_probability_pct,
            temp_max_c=day_summary.temp_max_c,
            et0_mm=day_summary.et0_mm,
            moisture_avg_pct=(sum(zm) / len(zm)) if zm else None,
            moisture_min_pct=min(zm) if zm else None,
            water_48h_m3=float(water_48h or 0.0),
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
                    if p.get("target_date") == date_str:
                        return s
                except Exception:
                    pass

    # Generate bilingual explanation via LLM agent (or rule-based fallback)
    suggestion_model = await run_weather_advisor(
        forecast=forecast,
        target_date=date_str,
        affected_zones=affected_zones,
        program_id=first_prog_id,
        db=db,
        lang=lang,
        decision=decision,
    )
    # Safety: the action is the server's decision, never the model's
    suggestion_model.action = decision.action
    suggestion_model.duration_factor = decision.duration_factor
    suggestion_model.affected_zone_ids = affected_zones
    if suggestion_model.provider_used == "rule_based":
        from app.services.ai.advisor_rules import explain

        (
            suggestion_model.title,
            suggestion_model.title_ar,
            suggestion_model.reasoning,
            suggestion_model.reasoning_ar,
        ) = explain(decision)

    action_payload = {
        "action": suggestion_model.action,
        "target_date": suggestion_model.target_date,
        "duration_factor": suggestion_model.duration_factor,
        "affected_zone_ids": suggestion_model.affected_zone_ids,
        "program_id": suggestion_model.program_id,
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
        priority="high" if suggestion_model.action == "skip" else "medium",
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
            "action": suggestion_model.action,
            "target_date": date_str,
            "title": suggestion.title,
        },
    )
    await manager.broadcast(
        "ai.suggestion.new",
        {
            "id": suggestion.id,
            "feature": "weather_advisor",
            "action": suggestion_model.action,
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

    target_date = payload.get("target_date", now_farm.strftime("%Y-%m-%d"))
    action = payload.get("action", "skip")
    factor = float(payload.get("duration_factor", 0.0 if action == "skip" else 1.2))
    program_id = payload.get("program_id")

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

    suggestion.status = "approved"
    suggestion.responded_at = now_farm
    suggestion.responded_by = operator_name

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
