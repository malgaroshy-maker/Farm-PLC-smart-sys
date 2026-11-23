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
  - GET  /api/v1/ai/settings & PUT /api/v1/ai/settings
  - GET  /api/v1/ai/models
"""

import asyncio
import json
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pydantic_ai import Agent
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.database import async_session_factory, get_db
from app.deps import Actor, get_actor, require_roles
from app.models.ai import AISettings, AISuggestion
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.zone import Zone
from app.services.ai import (
    AICallRecord,
    AISettingsResponse,
    AISettingsUpdateRequest,
    AlarmExplainRequest,
    AlarmExplanation,
    ChatRequest,
    ChatResponse,
    approve_suggestion,
    chat,
    evaluate_weather_advisor,
    explain_alarm,
    fetch_apinex_models,
    get_fallback_model,
    get_model_catalog,
    get_or_generate_daily_briefing,
    get_primary_model,
    get_recent_ai_calls,
    mark_model_available,
    mark_model_unavailable,
    reject_suggestion,
)
from app.services.anomaly import anomaly_detector
from app.services.weather import WeatherForecast, weather_service

router = APIRouter(prefix="/ai", tags=["AI"])
require_operator = require_roles("owner_admin", "operator")


def feature_on(key: str):
    """Dependency: 403 `feature_disabled:<key>` when the owner switched the feature off."""

    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        from app.services.features import is_enabled

        if not await is_enabled(db, key):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"feature_disabled:{key}")

    return Depends(_check)


require_admin = require_roles("owner_admin")

# ── Per-User Rate Limiting (30 requests/minute) ─────────────

_RATE_LIMIT_STORE: dict[str, deque[float]] = {}
AI_RATE_LIMIT_MAX = 30
AI_RATE_LIMIT_WINDOW_SEC = 60.0


def enforce_ai_rate_limit(actor: Actor = Depends(get_actor)) -> Actor:
    """Enforce per-user sliding window rate limit on AI endpoints."""
    now = time.monotonic()
    key = str(actor.actor_id or actor.name or "anonymous")
    if key not in _RATE_LIMIT_STORE:
        _RATE_LIMIT_STORE[key] = deque()

    q = _RATE_LIMIT_STORE[key]
    while q and (now - q[0]) > AI_RATE_LIMIT_WINDOW_SEC:
        q.popleft()

    if len(q) >= AI_RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for AI endpoints. Please wait before submitting more requests.",
        )

    q.append(now)
    return actor


def reset_ai_rate_limits() -> None:
    """Reset rate limit store (for tests)."""
    _RATE_LIMIT_STORE.clear()


# ── Feature 1: Alarm Explanation ────────────────────────────


@router.post(
    "/explain-alarm", response_model=AlarmExplanation, dependencies=[feature_on("ai.alarm_explain")]
)
@router.post(
    "/alarm-assistant",
    response_model=AlarmExplanation,
    dependencies=[feature_on("ai.alarm_explain")],
)
async def api_explain_alarm(
    body: AlarmExplainRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(enforce_ai_rate_limit),
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
                "current_value": alarm.current_value,
                "threshold_value": alarm.threshold_value,
                "zone_id": alarm.zone_id,
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


@router.post("/chat", response_model=ChatResponse, dependencies=[feature_on("ai.chat")])
async def api_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(enforce_ai_rate_limit),
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
            "action_payload": json.loads(s.action_payload_json) if s.action_payload_json else {},
            "zone_id": s.zone_id,
            "device_id": s.device_id,
            "confidence": s.confidence,
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "responded_at": s.responded_at.isoformat() if s.responded_at else None,
            "responded_by": s.responded_by,
        }
        for s in rows
    ]


@router.post("/suggestions/evaluate", dependencies=[feature_on("ai.advisor")])
async def api_evaluate_advisor(
    target_date: str | None = Query(None),
    program_id: str | None = Query(None),
    lang: str = Query("ar"),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_operator),
):
    """Trigger on-demand weather advisor evaluation for target date."""
    target = target_date or clock.farm_now().strftime("%Y-%m-%d")
    suggestion = await evaluate_weather_advisor(
        db=db,
        target_date=target,
        lang=lang,
    )

    if not suggestion:
        return {
            "status": "no_suggestion",
            "message": "Weather conditions normal; no irrigation adjustments required.",
        }

    return {
        "status": suggestion.status,
        "id": suggestion.id,
        "suggestion": {
            "id": suggestion.id,
            "title": suggestion.title,
            "title_ar": suggestion.title_ar,
            "description": suggestion.description,
            "description_ar": suggestion.description_ar,
            "action_payload": json.loads(suggestion.action_payload_json or "{}"),
            "priority": suggestion.priority,
            "confidence": suggestion.confidence,
        },
    }


@router.post("/suggestions/{suggestion_id}/approve")
async def api_approve_suggestion(
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_operator),
):
    """Operator approves suggestion and creates one-day scheduler override."""
    try:
        override = await approve_suggestion(db, suggestion_id, operator_name=actor.name)
        return {
            "status": "approved",
            "suggestion_id": override.suggestion_id,
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


@router.get("/briefing", dependencies=[feature_on("ai.briefing")])
@router.get("/insights/daily", dependencies=[feature_on("ai.briefing")])
async def api_get_daily_briefing(
    target_date: str | None = Query(None, alias="date"),
    force_refresh: bool = Query(False),
    lang: str = Query("ar"),
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve or generate daily operations briefing for target date."""
    target = target_date or clock.farm_now().strftime("%Y-%m-%d")
    record = await get_or_generate_daily_briefing(
        db=db,
        target_date=target,
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


async def _get_or_create_settings(db: AsyncSession) -> AISettings:
    stmt = select(AISettings).where(AISettings.id == "default")
    res = await db.execute(stmt)
    entry = res.scalar_one_or_none()
    if not entry:
        entry = AISettings(
            id="default",
            global_enabled=True,
            primary_provider="apinex",
            fallback_provider="gemini",
            apinex_base_url=settings.apinex_base_url,
            apinex_model=settings.apinex_model or "free/gemini-3.8-flash",
            apinex_fallback_model=settings.apinex_fallback_model or "free/glm-5.3-flash",
            gemini_model=settings.gemini_model,
            model_alarm="",
            model_advisor="",
            model_briefing="",
            model_chat="",
            alarm_assistant_enabled=True,
            smart_scheduling_enabled=True,
            predictive_maintenance_enabled=True,
            anomaly_detection_enabled=True,
            weather_advisor_enabled=True,
            water_optimizer_enabled=True,
            daily_insights_enabled=True,
            offline_fallback=settings.ai_offline_fallback,
            timeout_sec=settings.ai_timeout_sec,
            advisor_timeout_sec=settings.ai_advisor_timeout_sec,
            token_budget=settings.ai_token_budget,
            daily_briefing_time=settings.ai_daily_briefing_time,
            updated_at=clock.farm_now(),
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
    return entry


@router.get("/settings", response_model=AISettingsResponse)
async def api_get_ai_settings(
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve AI configuration, active models, coordinates, thresholds, and recent calls."""
    entry = await _get_or_create_settings(db)
    recent_calls = [AICallRecord(**c) for c in get_recent_ai_calls()]
    key_status = {
        "apinex": bool(settings.apinex_api_key),
        "gemini": bool(settings.gemini_api_key),
    }

    return AISettingsResponse(
        global_enabled=entry.global_enabled,
        primary_provider=entry.primary_provider,
        fallback_provider=entry.fallback_provider,
        apinex_base_url=entry.apinex_base_url,
        apinex_model=entry.apinex_model,
        apinex_fallback_model=entry.apinex_fallback_model,
        gemini_model=entry.gemini_model,
        model_alarm=entry.model_alarm,
        model_advisor=entry.model_advisor,
        model_briefing=entry.model_briefing,
        model_chat=entry.model_chat,
        alarm_assistant_enabled=entry.alarm_assistant_enabled,
        smart_scheduling_enabled=entry.smart_scheduling_enabled,
        predictive_maintenance_enabled=entry.predictive_maintenance_enabled,
        anomaly_detection_enabled=entry.anomaly_detection_enabled,
        weather_advisor_enabled=entry.weather_advisor_enabled,
        water_optimizer_enabled=entry.water_optimizer_enabled,
        daily_insights_enabled=entry.daily_insights_enabled,
        offline_fallback=entry.offline_fallback,
        timeout_sec=entry.timeout_sec,
        advisor_timeout_sec=entry.advisor_timeout_sec,
        token_budget=entry.token_budget,
        daily_briefing_time=entry.daily_briefing_time,
        weather_provider=settings.weather_api_provider,
        weather_coordinates={
            "latitude": settings.weather_latitude,
            "longitude": settings.weather_longitude,
        },
        weather_timezone=settings.weather_timezone,
        key_status=key_status,
        recent_calls=recent_calls,
    )


@router.put("/settings", response_model=AISettingsResponse)
async def api_update_ai_settings(
    body: AISettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(require_admin),
):
    """Update AI persistent configuration and feature toggles (Admin only)."""
    entry = await _get_or_create_settings(db)

    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if hasattr(entry, k) and v is not None:
            setattr(entry, k, v)
    entry.updated_at = clock.farm_now()
    await db.commit()
    await db.refresh(entry)

    # Sync runtime settings
    if body.apinex_model:
        settings.apinex_model = body.apinex_model
    if body.gemini_model:
        settings.gemini_model = body.gemini_model
    if body.timeout_sec is not None:
        settings.ai_timeout_sec = body.timeout_sec
    if body.advisor_timeout_sec is not None:
        settings.ai_advisor_timeout_sec = body.advisor_timeout_sec

    recent_calls = [AICallRecord(**c) for c in get_recent_ai_calls()]
    key_status = {
        "apinex": bool(settings.apinex_api_key),
        "gemini": bool(settings.gemini_api_key),
    }

    return AISettingsResponse(
        global_enabled=entry.global_enabled,
        primary_provider=entry.primary_provider,
        fallback_provider=entry.fallback_provider,
        apinex_base_url=entry.apinex_base_url,
        apinex_model=entry.apinex_model,
        apinex_fallback_model=entry.apinex_fallback_model,
        gemini_model=entry.gemini_model,
        model_alarm=entry.model_alarm,
        model_advisor=entry.model_advisor,
        model_briefing=entry.model_briefing,
        model_chat=entry.model_chat,
        alarm_assistant_enabled=entry.alarm_assistant_enabled,
        smart_scheduling_enabled=entry.smart_scheduling_enabled,
        predictive_maintenance_enabled=entry.predictive_maintenance_enabled,
        anomaly_detection_enabled=entry.anomaly_detection_enabled,
        weather_advisor_enabled=entry.weather_advisor_enabled,
        water_optimizer_enabled=entry.water_optimizer_enabled,
        daily_insights_enabled=entry.daily_insights_enabled,
        offline_fallback=entry.offline_fallback,
        timeout_sec=entry.timeout_sec,
        advisor_timeout_sec=entry.advisor_timeout_sec,
        token_budget=entry.token_budget,
        daily_briefing_time=entry.daily_briefing_time,
        weather_provider=settings.weather_api_provider,
        weather_coordinates={
            "latitude": settings.weather_latitude,
            "longitude": settings.weather_longitude,
        },
        weather_timezone=settings.weather_timezone,
        key_status=key_status,
        recent_calls=recent_calls,
    )


class AITestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    prompt: str | None = None


class AITestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    model_used: str
    latency_ms: float
    error: str | None = None


@router.post("/test", response_model=AITestResponse)
async def api_test_ai(
    body: AITestRequest | None = None,
    actor: Actor = Depends(require_admin),
):
    """Test AI model connection and measure response latency (admin only)."""
    # Default to the settings saved in the admin page (DB), then .env.
    async with async_session_factory() as db:
        saved = await db.get(AISettings, "default")
    target_provider = (
        (body.provider if body and body.provider else None)
        or (saved.primary_provider if saved else None)
        or settings.primary_provider
        or "apinex"
    ).lower()
    target_model = (
        (body.model if body and body.model else None)
        or (saved.apinex_model if saved and target_provider == "apinex" else None)
        or (saved.gemini_model if saved and target_provider != "apinex" else None)
        or (settings.apinex_model if target_provider == "apinex" else settings.gemini_model)
    )
    test_prompt = body.prompt if body and body.prompt else "Test connection. Reply with OK."

    t0 = time.monotonic()
    try:
        if target_provider == "apinex":
            llm_model = get_primary_model(model_name=target_model)
        else:
            llm_model = get_fallback_model(model_name=target_model)

        test_agent = Agent(model=llm_model)
        await asyncio.wait_for(test_agent.run(test_prompt), timeout=15.0)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        mark_model_available(target_model)
        return AITestResponse(
            ok=True,
            provider=target_provider,
            model=target_model,
            model_used=target_model,
            latency_ms=latency_ms,
            error=None,
        )
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        err_msg = str(exc)
        if any(code in err_msg for code in ("400", "402")):
            mark_model_unavailable(target_model, f"HTTP error during test: {err_msg[:100]}")
        return AITestResponse(
            ok=False,
            provider=target_provider,
            model=target_model,
            model_used=target_model,
            latency_ms=latency_ms,
            error=err_msg,
        )


@router.get("/baselines/{zone_id}")
async def api_get_zone_baseline(
    zone_id: str,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Retrieve real hydraulic baseline statistics for an irrigation zone using AnomalyDetector."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        stmt = select(Zone).where((Zone.id == zone_id) | (Zone.code == zone_id))
        res = await db.execute(stmt)
        zone = res.scalar_one_or_none()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_id}' not found",
        )

    # Query completed cycles for zone
    c_stmt = (
        select(IrrigationCycle)
        .where(IrrigationCycle.zone_id == zone.id, IrrigationCycle.outcome == "completed")
        .order_by(desc(IrrigationCycle.actual_end_at))
    )
    c_res = await db.execute(c_stmt)
    completed_cycles = list(c_res.scalars().all())
    runs_completed = len(completed_cycles)
    runs_required = 5
    calibrated = runs_completed >= runs_required

    # Retrieve or compute baseline
    baseline = anomaly_detector.get_baseline(zone.id)
    if not baseline and runs_completed >= anomaly_detector.min_baseline_runs:
        baseline = await anomaly_detector.compute_zone_baseline_from_db(db, zone.id, max_cycles=20)

    if calibrated and baseline:
        flow_med = round(baseline.flow.median, 2)
        flow_mad = round(baseline.flow.mad, 2)
        flow_min = round(max(0.0, baseline.flow.median - 2.0 * baseline.flow.scale), 2)
        flow_max = round(baseline.flow.median + 2.0 * baseline.flow.scale, 2)
        press_med = round(baseline.pressure.median, 2)
        press_mad = round(baseline.pressure.mad, 2)
        press_min = round(max(0.0, baseline.pressure.median - 2.0 * baseline.pressure.scale), 2)
        press_max = round(baseline.pressure.median + 2.0 * baseline.pressure.scale, 2)

        return {
            "zone_id": zone.id,
            "calibrated": True,
            "is_calibrated": True,
            "runs_completed": runs_completed,
            "runs_required": runs_required,
            "baseline_cycles_count": runs_completed,
            "flow_median_m3h": flow_med,
            "flow_mad_m3h": flow_mad,
            "flow_min_normal_m3h": flow_min,
            "flow_max_normal_m3h": flow_max,
            "pressure_median_bar": press_med,
            "pressure_mad_bar": press_mad,
            "pressure_min_normal_bar": press_min,
            "pressure_max_normal_bar": press_max,
            "status": "normal",
            "message": f"Calibrated ({runs_completed}/5 runs)",
        }

    return {
        "zone_id": zone.id,
        "calibrated": False,
        "is_calibrated": False,
        "runs_completed": runs_completed,
        "runs_required": runs_required,
        "baseline_cycles_count": runs_completed,
        "flow_median_m3h": round(baseline.flow.median, 2) if baseline else None,
        "flow_mad_m3h": round(baseline.flow.mad, 2) if baseline else None,
        "flow_min_normal_m3h": None,
        "flow_max_normal_m3h": None,
        "pressure_median_bar": round(baseline.pressure.median, 2) if baseline else None,
        "pressure_mad_bar": round(baseline.pressure.mad, 2) if baseline else None,
        "pressure_min_normal_bar": None,
        "pressure_max_normal_bar": None,
        "status": "insufficient_data",
        "message": f"not enough data yet ({runs_completed}/5 runs)",
    }


@router.get("/models")
async def api_get_models(actor: Actor = Depends(get_actor)):
    """Fetch available models dynamically from APInex with catalog badges and metadata."""
    models = await fetch_apinex_models()
    catalog = [m.model_dump() for m in get_model_catalog(models)]
    selected = settings.apinex_model or "free/deepseek-v4-pro-0813"
    return {
        "models": models,
        "catalog": catalog,
        "selected": selected,
        "fallback": settings.gemini_model,
    }


# ── Usage view (Milestone G2) ────────────────────────────────


@router.get("/usage")
async def api_ai_usage(
    days: int = Query(7, ge=1, le=90),
    _: Actor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """AI calls over the last `days` (real time): speed, fallbacks and tokens per feature and model."""
    from datetime import timedelta

    from app.core.timeutil import utcnow
    from app.models.ai import AICallLog

    since = utcnow() - timedelta(days=days)
    rows = (
        (await db.execute(select(AICallLog).where(AICallLog.ts >= since).order_by(AICallLog.ts)))
        .scalars()
        .all()
    )

    def summarize(items: list) -> dict[str, Any]:
        lat = sorted(r.latency_ms for r in items)
        fb = [r for r in items if r.fallback_reason]
        return {
            "calls": len(items),
            "fallbacks": len(fb),
            "rule_based": sum(1 for r in items if r.provider == "rule_based"),
            "avg_ms": round(sum(lat) / len(lat)) if lat else 0,
            "p95_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))]) if lat else 0,
            "requests": sum(r.requests or 0 for r in items),
            "input_tokens": sum(r.input_tokens or 0 for r in items),
            "output_tokens": sum(r.output_tokens or 0 for r in items),
        }

    def group(key) -> list[dict[str, Any]]:
        out: dict[str, list] = {}
        for r in rows:
            out.setdefault(key(r), []).append(r)
        return sorted(
            ({"name": k, **summarize(v)} for k, v in out.items()), key=lambda x: -x["calls"]
        )

    reasons: dict[str, int] = {}
    for r in rows:
        if r.fallback_reason:
            k = r.fallback_reason.split(":", 1)[0]
            reasons[k] = reasons.get(k, 0) + 1

    return {
        "days": days,
        "total": summarize(list(rows)),
        "by_feature": group(lambda r: r.feature),
        "by_model": group(lambda r: r.model if r.provider != "rule_based" else "rule_based"),
        "fallback_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "recent": [
            {
                "ts": r.ts.isoformat(),
                "feature": r.feature,
                "provider": r.provider,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "fallback_reason": r.fallback_reason,
                "requests": r.requests,
                "tokens": (r.input_tokens or 0) + (r.output_tokens or 0),
            }
            for r in list(rows)[-20:][::-1]
        ],
    }
