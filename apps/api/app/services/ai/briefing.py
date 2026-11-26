"""Daily Briefing Service on Farm Clock (Milestone E).

Generates automated morning briefings at 06:00 farm time (clock.farm_now()).
Caches and persists reports in the DB (ai_briefings and ai_insights tables).
"""

import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.clock import clock
from app.models.ai import AIBriefing, AIInsight, ProgramOverride
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.program import Program, ProgramStep
from app.services.ai.agent import run_daily_briefing
from app.services.ai.arabic import normalize_text
from app.services.alarms import OPEN
from app.services.conflicts import parse_time_minutes, parse_weekday_mask
from app.services.events import log_event
from app.services.realtime import manager
from app.services.weather import is_usable_forecast, weather_service

log = logging.getLogger(__name__)


async def get_briefing_schedule(db: AsyncSession, briefing_date: str) -> list[dict] | None:
    """Read the current farm day's configured program plan, including approved overrides."""
    today = clock.farm_now().astimezone(ZoneInfo(settings.farm_timezone)).date()
    if briefing_date != today.isoformat():
        return None

    configured = await db.scalars(
        select(Program)
        .where(Program.enabled.is_(True))
        .options(selectinload(Program.steps).joinedload(ProgramStep.zone))
        .order_by(Program.id)
    )
    programs = [
        program
        for program in configured
        if program.steps and today.isoweekday() in parse_weekday_mask(program.weekday_mask)
    ]
    if not programs:
        return []

    overrides = await db.scalars(
        select(ProgramOverride)
        .where(ProgramOverride.target_date == briefing_date)
        .order_by(ProgramOverride.applied.desc(), ProgramOverride.created_at.desc())
    )
    by_program = {}
    for override in overrides:
        if override.program_id is None:
            # A legacy one-shot override can affect whichever program runs first.
            return None
        by_program.setdefault(override.program_id, override)

    plan = []
    for program in programs:
        override = by_program.get(program.id)
        if override and override.action == "skip":
            continue
        try:
            hours, minutes = divmod(parse_time_minutes(program.start_time_local), 60)
        except ValueError:
            continue
        plan.append(
            {
                "program_id": program.id,
                "program_name": program.name,
                "start_time": f"{hours:02d}:{minutes:02d}",
                "zones": [step.zone.name if step.zone else step.zone_id for step in program.steps],
                "action": override.action if override else None,
            }
        )
    return sorted(plan, key=lambda item: item["start_time"])


async def get_or_generate_daily_briefing(
    db: AsyncSession,
    target_date: str | None = None,
    force_refresh: bool = False,
    lang: str = "ar",
) -> AIBriefing:
    """Retrieve existing briefing or generate a new one for target_date."""
    now_farm = clock.farm_now()
    farm_tz = ZoneInfo(settings.farm_timezone)
    day = date.fromisoformat(target_date) if target_date else now_farm.astimezone(farm_tz).date()
    date_str = day.isoformat()

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
        if existing and json.loads(existing.payload_json or "{}").get("facts_version") == 2:
            # briefings stored before the G2 normalizer may hold Arabic-Indic digits
            for field in ("summary_ar", "weather_summary_ar"):
                val = getattr(existing, field, None)
                if isinstance(val, str):
                    setattr(existing, field, normalize_text(val))
            return existing

    # The briefing for a farm-local date summarizes the previous calendar day.
    end = datetime.combine(day, time.min, tzinfo=farm_tz).astimezone(UTC)
    cutoff = datetime.combine(day - timedelta(days=1), time.min, tzinfo=farm_tz).astimezone(UTC)

    # Cycles
    started = func.coalesce(IrrigationCycle.actual_start_at, IrrigationCycle.created_at)
    c_stmt = (
        select(IrrigationCycle)
        .where(
            started >= cutoff,
            started < end,
            ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
        )
        .order_by(desc(IrrigationCycle.created_at))
    )
    c_res = await db.execute(c_stmt)
    cycles_models = list(c_res.scalars().all())
    cycles_dicts = [
        {
            "id": c.id,
            "zone_id": c.zone_id,
            "outcome": c.outcome,
            "water_volume_m3": c.water_estimate_m3,
            "water_is_estimate": c.water_is_estimate,
            "duration_minutes": c.actual_duration_min,
        }
        for c in cycles_models
    ]

    # Alarms
    from app.core.alarm_catalog import CATALOG

    a_stmt = select(Alarm).where(
        ((Alarm.triggered_at >= cutoff) & (Alarm.triggered_at < end)) | Alarm.status.in_(OPEN)
    )
    a_res = await db.execute(a_stmt)
    alarms_models = list(a_res.scalars().all())
    alarms_dicts = [
        {
            "id": a.id,
            "alarm_code": a.alarm_code,
            "severity": a.severity,
            "status": a.status,
            "name": CATALOG[a.alarm_code].name if a.alarm_code in CATALOG else a.alarm_code,
            "name_ar": CATALOG[a.alarm_code].name_ar if a.alarm_code in CATALOG else a.alarm_code,
        }
        for a in alarms_models
    ]

    # Weather
    forecast = await weather_service.get_forecast(db=db)
    forecast_day = (
        next((item for item in forecast.daily if item.date == date_str), None)
        if forecast and is_usable_forecast(forecast)
        else None
    )
    valid_forecast = forecast if forecast_day else None
    known_volumes = [
        row["water_volume_m3"] for row in cycles_dicts if row["water_volume_m3"] is not None
    ]
    metrics = {
        "water_used_yesterday_m3": sum(known_volumes)
        if known_volumes and len(known_volumes) == len(cycles_dicts)
        else None,
        "water_is_estimate": any(
            row["water_is_estimate"] for row in cycles_dicts if row["water_volume_m3"] is not None
        ),
        "weather_forecast": (
            {
                "condition": forecast_day.condition,
                "temp_min_c": forecast_day.temp_min_c,
                "temp_max_c": forecast_day.temp_max_c,
                "rain_prob_pct": forecast_day.precipitation_probability_pct,
                "precipitation_mm": forecast_day.precipitation_total_mm,
                "et0_mm": forecast_day.et0_mm,
            }
            if forecast_day
            else None
        ),
        "alarms_summary": {"active_count": sum(row["status"] in OPEN for row in alarms_dicts)},
    }

    # 3. Generate structured briefing via Pydantic AI agent (or rule-based fallback)
    briefing_data = await run_daily_briefing(
        date_str=date_str,
        cycles=cycles_dicts,
        alarms=alarms_dicts,
        forecast=valid_forecast,
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
        payload_json=json.dumps(
            {**briefing_data.model_dump(), "facts_version": 2, "metrics": metrics}
        ),
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


async def check_scheduled_briefing(
    db: AsyncSession,
    prev_farm: datetime | None = None,
    now_farm: datetime | None = None,
) -> AIBriefing | None:
    """Invoked on farm monitor ticks to trigger morning briefing at 06:00 farm time."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(settings.farm_timezone)
    current_farm = (now_farm or clock.farm_now()).astimezone(tz)  # farm-local, not UTC
    farm_time_hm = current_farm.strftime("%H:%M")
    target_time_hm = settings.ai_daily_briefing_time  # "06:00"

    # If called from scheduler tick with prev_farm and now_farm, check if target time crossed
    if prev_farm is not None and now_farm is not None:
        target_h, target_m = (int(x) for x in target_time_hm.split(":"))
        target_dt = current_farm.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if not (prev_farm.astimezone(tz) < target_dt <= current_farm):
            return None
    else:
        # Only run once the farm clock reaches or passes target time
        if farm_time_hm < target_time_hm:
            return None

    today_date = current_farm.strftime("%Y-%m-%d")

    # Check if today's briefing is already generated
    stmt = select(AIBriefing.id).where(AIBriefing.date == today_date).limit(1)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return None

    log.info("Generating daily farm briefing for %s at farm time %s", today_date, farm_time_hm)
    briefing = await get_or_generate_daily_briefing(db, target_date=today_date)
    try:
        from app.services.notify import Notification, notify_in_background

        b = briefing if isinstance(briefing, dict) else getattr(briefing, "__dict__", {})
        title_ar = b.get("title_ar") or "الموجز الصباحي للمزرعة"
        notify_in_background(
            Notification(
                kind="briefing",
                title_ar=str(title_ar),
                title_en=str(b.get("title") or "Morning farm briefing"),
                body_ar=str(b.get("summary_ar") or "")[:600],
                body_en=str(b.get("summary") or "")[:300],
            )
        )
    except Exception:  # pragma: no cover - notifying must never break the briefing
        log.exception("could not send the briefing notification")
    return briefing
