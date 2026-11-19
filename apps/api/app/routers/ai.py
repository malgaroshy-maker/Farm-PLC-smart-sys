"""AI Services Router — /api/v1/ai (Milestone E).

Endpoints:
  - POST /api/v1/ai/explain-alarm (and /alarm-assistant)
  - POST /api/v1/ai/chat
  - GET  /api/v1/ai/suggestions
  - POST /api/v1/ai/suggestions/evaluate
  - POST /api/v1/ai/suggestions/{id}/approve
  - POST /api/v1/ai/suggestions/{id}/reject
  - GET  /api/v1/ai/briefing (and /insights/daily)
  - GET  /api/v1/ai/weather/forecast & /current
  - GET  /api/v1/ai/settings & /models
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import Actor, get_actor, require_roles
from app.models.ai import AISuggestion
from app.models.alarm import Alarm
from app.services.ai import (
    AISettingsResponse,
    AlarmExplainRequest,
    AlarmExplanation,
    ChatRequest,
    ChatResponse,
    approve_suggestion,
    chat,
    evaluate_weather_advisor,
    explain_alarm,
    fetch_apinex_models,
    get_or_generate_daily_briefing,
    reject_suggestion,
)
from app.services.weather import WeatherForecast, weather_service

router = APIRouter(prefix="/ai", tags=["AI"])
require_operator = require_roles("owner_admin", "operator")


# ── Feature 1: Alarm Explanation ────────────────────────────


@router.post("/explain-alarm", response_model=AlarmExplanation)
@router.post("/alarm-assistant", response_model=AlarmExplanation)
async def api_explain_alarm(
    body: AlarmExplainRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Diagnose an alarm and return structured explanation and fix guidance."""
    alarm_data: dict[str, Any] = {}

    if body.alarm_id:
        alarm = await db.get(Alarm, body.alarm_id)
        if not alarm:
            # Check by code
            res = await db.execute(select(Alarm).where(Alarm.alarm_code == body.alarm_id).limit(1))
            alarm = res.scalar_one_or_none()

        if alarm:
            alarm_data = {
                "id": alarm.id,
                "alarm_code": alarm.alarm_code,
                "name": alarm.name,
                "name_ar": alarm.name_ar,
                "severity": alarm.severity,
                "category": alarm.category,
                "current_value": alarm.current_value,
                "threshold_value": alarm.threshold_value,
                "guidance_en": alarm.guidance_en,
                "guidance_ar": alarm.guidance_ar,
            }

    if not alarm_data and body.alarm_code:
        alarm_data = {"alarm_code": body.alarm_code}

    if not alarm_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either alarm_id or alarm_code must be provided",
        )

    return await explain_alarm(alarm_data=alarm_data, db=db, lang=body.language)


# ── Chat Assistant ───────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def api_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Interactive bilingual farm assistant."""
    return await chat(
        message=body.message,
        history=body.history,
        context_zone_id=body.context_zone_id,
        db=db,
        lang=body.language,
    )


# ── Feature 2 & 5: Weather Advisor & Suggestions ─────────────


@router.get("/suggestions")
async def api_list_suggestions(
    feature: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """List AI suggestions with optional filtering."""
    stmt = select(AISuggestion).order_by(desc(AISuggestion.created_at))
    if feature:
        stmt = stmt.where(AISuggestion.feature == feature)
    if status_filter:
        stmt = stmt.where(AISuggestion.status == status_filter)

    res = await db.execute(stmt)
    rows = res.scalars().all()

    return [
        {
            "id": s.id,
            "feature": s.feature,
            "priority": s.priority,
            "status": s.status,
            "title": s.title,
            "title_ar": s.title_ar,
            "description": s.description,
            "description_ar": s.description_ar,
            "reasoning": s.reasoning,
            "reasoning_ar": s.reasoning_ar,
            "action_payload": json.loads(s.action_payload_json) if s.action_payload_json else None,
            "zone_id": s.zone_id,
            "confidence": s.confidence,
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "responded_at": s.responded_at.isoformat() if s.responded_at else None,
            "responded_by": s.responded_by,
        }
        for s in rows
    ]


@router.post("/suggestions/evaluate")
async def api_evaluate_advisor(
    target_date: str | None = Query(None),
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_operator),
):
    """Trigger weather advisor evaluation now."""
    suggestion = await evaluate_weather_advisor(
        db=db,
        target_date=target_date,
        force_refresh=force_refresh,
    )
    if not suggestion:
        return {"message": "Weather conditions are normal. No adjustment suggestions needed."}

    return {
        "id": suggestion.id,
        "title": suggestion.title,
        "title_ar": suggestion.title_ar,
        "status": suggestion.status,
        "action_payload": json.loads(suggestion.action_payload_json or "{}"),
    }


@router.post("/suggestions/{suggestion_id}/approve")
async def api_approve_suggestion(
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_operator),
):
    """Operator approves suggestion -> creates one-day ProgramOverride for scheduler."""
    try:
        override = await approve_suggestion(db, suggestion_id, operator_name=actor.name)
        return {
            "status": "approved",
            "suggestion_id": suggestion_id,
            "override_id": override.id,
            "target_date": override.target_date,
            "action": override.action,
            "duration_factor": override.duration_factor,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/suggestions/{suggestion_id}/reject")
async def api_reject_suggestion(
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_operator),
):
    """Operator rejects suggestion."""
    try:
        suggestion = await reject_suggestion(db, suggestion_id, operator_name=actor.name)
        return {
            "status": "rejected",
            "suggestion_id": suggestion.id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ── Feature 7: Daily Briefing & Insights ─────────────────────


@router.get("/briefing")
@router.get("/insights/daily")
async def api_get_daily_briefing(
    date: str | None = Query(None),
    force_refresh: bool = Query(False),
    lang: str = Query("ar"),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve or generate daily operations briefing for specified farm date."""
    record = await get_or_generate_daily_briefing(
        db=db,
        target_date=date,
        force_refresh=force_refresh,
        lang=lang,
    )

    recs = json.loads(record.recommendations_json or "[]")
    return {
        "id": record.id,
        "date": record.date,
        "title": record.title,
        "title_ar": record.title_ar,
        "summary": record.summary,
        "summary_ar": record.summary_ar,
        "weather_summary": record.weather_summary,
        "weather_summary_ar": record.weather_summary_ar,
        "irrigation_overview": record.irrigation_overview,
        "irrigation_overview_ar": record.irrigation_overview_ar,
        "alarms_overview": record.alarms_overview,
        "alarms_overview_ar": record.alarms_overview_ar,
        "recommendations": recs,
        "provider_used": record.provider_used,
        "created_at": record.created_at.isoformat(),
    }


# ── Weather ──────────────────────────────────────────────────


@router.get("/weather/forecast", response_model=WeatherForecast)
async def api_get_weather_forecast(
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve 7-day weather forecast from Open-Meteo with 3h caching."""
    return await weather_service.get_forecast(db=db, force_refresh=force_refresh)


@router.get("/weather/current")
async def api_get_current_weather(
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve current weather conditions for Algaroshy Farm."""
    fc = await weather_service.get_forecast(db=db)
    return fc.current


# ── Settings & Models ────────────────────────────────────────


@router.get("/settings", response_model=AISettingsResponse)
async def api_get_ai_settings(actor: Actor = Depends(get_actor)):
    """Retrieve AI configuration, active models, coordinates, and thresholds."""
    return AISettingsResponse(
        primary_provider="apinex",
        fallback_provider="gemini",
        apinex_base_url=settings.apinex_base_url,
        apinex_model=settings.apinex_model or "gpt-4o-mini",
        gemini_model=settings.gemini_model,
        offline_fallback=settings.ai_offline_fallback,
        timeout_sec=settings.ai_timeout_sec,
        token_budget=settings.ai_token_budget,
        daily_briefing_time=settings.ai_daily_briefing_time,
        weather_provider=settings.weather_api_provider,
        weather_coordinates={
            "latitude": settings.weather_latitude,
            "longitude": settings.weather_longitude,
        },
        weather_timezone=settings.weather_timezone,
    )


@router.get("/models")
async def api_get_models(actor: Actor = Depends(get_actor)):
    """Fetch available models dynamically from APInex."""
    models = await fetch_apinex_models()
    return {
        "models": models,
        "selected": settings.apinex_model or (models[0] if models else "gpt-4o-mini"),
        "fallback": settings.gemini_model,
    }
