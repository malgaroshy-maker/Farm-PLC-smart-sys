"""Daily Briefing Service on Farm Clock (Milestone E).

Generates automated morning briefings at 06:00 farm time (clock.farm_now()).
Caches and persists reports in the DB (ai_briefings and ai_insights tables).
"""

import json
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.models.ai import AIBriefing, AIInsight
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.services.ai.agent import run_daily_briefing
from app.services.events import log_event
from app.services.realtime import manager
from app.services.weather import weather_service

log = logging.getLogger(__name__)


async def get_or_generate_daily_briefing(
    db: AsyncSession,
    target_date: str | None = None,
    force_refresh: bool = False,
    lang: str = "ar",
) -> AIBriefing:
    """Retrieve existing briefing or generate a new one for target_date."""
    now_farm = clock.farm_now()
    date_str = target_date or now_farm.strftime("%Y-%m-%d")

    # 1. Check existing record in DB
    if not force_refresh:
        stmt = (
            select(AIBriefing)
            .where(AIBriefing.date == date_str)
            .order_by(desc(AIBriefing.created_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

    # 2. Gather context data from the past 24 hours
    cutoff = now_farm - timedelta(hours=24)

    # Cycles
    c_stmt = (
        select(IrrigationCycle)
        .where((IrrigationCycle.actual_start_at >= cutoff) | (IrrigationCycle.created_at >= cutoff))
        .order_by(desc(IrrigationCycle.created_at))
    )
    c_res = await db.execute(c_stmt)
    cycles_models = list(c_res.scalars().all())
    cycles_dicts = [
        {
            "id": c.id,
            "zone_id": c.zone_id,
            "outcome": c.outcome,
            "water_volume_m3": float(c.water_estimate_m3 or 0.0),
            "duration_minutes": float(c.actual_duration_min or 0.0),
        }
        for c in cycles_models
    ]

    # Alarms
    a_stmt = select(Alarm).where((Alarm.triggered_at >= cutoff) | (Alarm.status == "active"))
    a_res = await db.execute(a_stmt)
    alarms_models = list(a_res.scalars().all())
    alarms_dicts = [
        {
            "id": a.id,
            "alarm_code": a.alarm_code,
            "severity": a.severity,
            "status": a.status,
            "name": a.name,
            "name_ar": a.name_ar,
        }
        for a in alarms_models
    ]

    # Weather
    forecast = await weather_service.get_forecast(db=db)

    # 3. Generate structured briefing via Pydantic AI agent (or rule-based fallback)
    briefing_data = await run_daily_briefing(
        date_str=date_str,
        cycles=cycles_dicts,
        alarms=alarms_dicts,
        forecast=forecast,
        db=db,
        lang=lang,
    )

    # 4. Store in ai_briefings table
    record = AIBriefing(
        id=f"brief_{uuid4().hex[:12]}",
        date=date_str,
        title=briefing_data.title,
        title_ar=briefing_data.title_ar,
        summary=briefing_data.summary,
        summary_ar=briefing_data.summary_ar,
        weather_summary=briefing_data.weather_summary,
        weather_summary_ar=briefing_data.weather_summary_ar,
        irrigation_overview=briefing_data.irrigation_overview,
        irrigation_overview_ar=briefing_data.irrigation_overview_ar,
        alarms_overview=briefing_data.alarms_overview,
        alarms_overview_ar=briefing_data.alarms_overview_ar,
        recommendations_json=json.dumps(briefing_data.recommendations),
        payload_json=briefing_data.model_dump_json(),
        provider_used=briefing_data.provider_used,
        created_at=now_farm,
    )
    db.add(record)

    # Also record in ai_insights for UI contract compatibility
    insight = AIInsight(
        id=f"ins_{uuid4().hex[:12]}",
        insight_type="daily_summary",
        language=lang,
        date=date_str,
        title=briefing_data.title,
        title_ar=briefing_data.title_ar,
        summary=briefing_data.summary,
        summary_ar=briefing_data.summary_ar,
        sections_json=json.dumps(
            [
                {
                    "heading": "Weather",
                    "heading_ar": "الطقس",
                    "content": briefing_data.weather_summary,
                    "content_ar": briefing_data.weather_summary_ar,
                    "icon": "cloud",
                    "metrics": [],
                },
                {
                    "heading": "Irrigation",
                    "heading_ar": "الري",
                    "content": briefing_data.irrigation_overview,
                    "content_ar": briefing_data.irrigation_overview_ar,
                    "icon": "droplet",
                    "metrics": [],
                },
                {
                    "heading": "Alarms",
                    "heading_ar": "الإنذارات",
                    "content": briefing_data.alarms_overview,
                    "content_ar": briefing_data.alarms_overview_ar,
                    "icon": "alert",
                    "metrics": [],
                },
            ]
        ),
        generated_at=now_farm,
        generated_by=briefing_data.provider_used,
    )
    db.add(insight)

    await db.commit()
    await db.refresh(record)

    await log_event(
        db,
        "ai.insight.ready",
        "ai_briefing",
        record.id,
        actor_type="ai",
        payload={"date": date_str, "provider": record.provider_used},
    )
    await manager.broadcast(
        "ai.insight.ready",
        {
            "id": record.id,
            "date": date_str,
            "title": record.title,
            "title_ar": record.title_ar,
            "provider": record.provider_used,
        },
    )

    return record


async def check_scheduled_briefing(db: AsyncSession) -> AIBriefing | None:
    """Invoked on farm monitor ticks to trigger morning briefing at 06:00 farm time."""
    now_farm = clock.farm_now()
    farm_time_hm = now_farm.strftime("%H:%M")
    target_time_hm = settings.ai_daily_briefing_time  # "06:00"

    # Only run once the farm clock reaches or passes 06:00
    if farm_time_hm < target_time_hm:
        return None

    today_date = now_farm.strftime("%Y-%m-%d")

    # Check if today's briefing is already generated
    stmt = select(AIBriefing.id).where(AIBriefing.date == today_date).limit(1)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return None

    log.info("Generating daily farm briefing for %s at farm time %s", today_date, farm_time_hm)
    return await get_or_generate_daily_briefing(db, target_date=today_date)
