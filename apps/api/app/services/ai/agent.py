"""Pydantic AI Agents Core (Milestone E).

Implements:
  - Pydantic AI Agents with FallbackModel (APInex -> Gemini -> Rule-based)
  - Structured output models (AlarmExplanation, AdvisorSuggestion, DailyBriefing, ChatResponse)
  - Read-only tools for live context
  - 15s timeout, retry/backoff on 429/5xx, token budget, request caching
  - Strict payload redaction before sending
"""

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.timeutil import utcnow
from app.services.ai.providers import (
    build_fallback_chain,
    identify_provider_label,
)
from app.services.ai.redaction import redact_payload, redact_text
from app.services.ai.rules import rule_service
from app.services.ai.schemas import (
    AdvisorSuggestion,
    AlarmExplanation,
    ChatResponse,
    DailyBriefing,
)
from app.services.ai.tools import AI_TOOLS, AIDeps
from app.services.weather import WeatherForecast

log = logging.getLogger(__name__)

# Request Cache: (cache_key -> (timestamp, data))
_REQUEST_CACHE: dict[str, tuple[datetime, Any]] = {}
CACHE_TTL_SEC = 60.0


def _get_cache(key: str) -> Any | None:
    if key in _REQUEST_CACHE:
        ts, data = _REQUEST_CACHE[key]
        if (utcnow() - ts).total_seconds() < CACHE_TTL_SEC:
            return data
        del _REQUEST_CACHE[key]
    return None


def _set_cache(key: str, data: Any) -> None:
    # Cap cache size to 100 entries
    if len(_REQUEST_CACHE) > 100:
        oldest = min(_REQUEST_CACHE.keys(), key=lambda k: _REQUEST_CACHE[k][0])
        del _REQUEST_CACHE[oldest]
    _REQUEST_CACHE[key] = (utcnow(), data)


def clear_ai_cache() -> None:
    """Clear in-memory request cache (primarily for tests)."""
    _REQUEST_CACHE.clear()


def _make_cache_key(prefix: str, payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{h}"


# ── System Prompts ───────────────────────────────────────────

ALARM_SYSTEM_PROMPT = """
You are the AI Alarm Assistant for Algaroshy Farm (مزرعة الجروشي) Smart Irrigation System in Libya.
Your mission is to provide accurate, safe, bilingual (Arabic & English) root-cause diagnoses and step-by-step fix recommendations for farm alarms.
You have access to live read-only tools to inspect active alarms, zone states, and hydraulic telemetry.
Always maintain safety authority with the PLC: you only suggest, operators and PLC decide.
Respond strictly matching the structured AlarmExplanation schema.
"""

ADVISOR_SYSTEM_PROMPT = """
You are the Weather-Aware Irrigation Advisor for Algaroshy Farm (مزرعة الجروشي).
Evaluate deterministic thresholds and weather conditions (precipitation, heatwaves, FAO ET0 evapotranspiration) to propose schedule adjustments (skip, extend +20%, reduce, or maintain).
You have read-only tools to inspect weather forecast, schedules, and past cycles.
Never directly execute commands; propose a one-day override that operators can approve.
Respond strictly matching the structured AdvisorSuggestion schema.
"""

BRIEFING_SYSTEM_PROMPT = """
You are the Farm Operations AI Synthesizer for Algaroshy Farm (مزرعة الجروشي).
Compile concise, professional bilingual morning briefings summarizing water volume delivered, cycle completions/faults, active alarms, and daily weather outlook.
Respond strictly matching the structured DailyBriefing schema.
"""

CHAT_SYSTEM_PROMPT = """
You are the intelligent bilingual farm assistant for Algaroshy Farm (مزرعة الجروشي).
Answer operator queries about pumps, zones, crops (olives, pomegranates, palms, citrus), alarms, and weather.
Use read-only tools to retrieve real-time farm state.
Respond strictly matching the structured ChatResponse schema.
"""


# ── Pydantic AI Agents ───────────────────────────────────────

alarm_agent = Agent(
    model=build_fallback_chain(),
    output_type=AlarmExplanation,
    system_prompt=ALARM_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
)

advisor_agent = Agent(
    model=build_fallback_chain(),
    output_type=AdvisorSuggestion,
    system_prompt=ADVISOR_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
)

briefing_agent = Agent(
    model=build_fallback_chain(),
    output_type=DailyBriefing,
    system_prompt=BRIEFING_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
)

chat_agent = Agent(
    model=build_fallback_chain(),
    output_type=ChatResponse,
    system_prompt=CHAT_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
)


# ── Robust Execution Helper ─────────────────────────────────


async def _run_with_retry_and_fallback(
    agent_instance: Agent,
    prompt: str,
    deps: AIDeps,
    fallback_fn: Callable[[], Any],
    cache_key: str | None = None,
) -> Any:
    """Execute Pydantic AI agent with timeouts, exponential retry on 429/5xx, and rule fallback."""
    if cache_key:
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached

    # Strict Redaction before external dispatch
    safe_prompt = redact_text(prompt)

    retries = 0
    max_retries = max(0, settings.ai_max_retries)
    backoff = 0.5

    while True:
        try:
            # Enforce 15s timeout
            result = await asyncio.wait_for(
                agent_instance.run(safe_prompt, deps=deps),
                timeout=settings.ai_timeout_sec,
            )
            data = result.output

            # Identify provider label
            provider_label = identify_provider_label(result.response)
            if hasattr(data, "provider_used"):
                data.provider_used = provider_label

            if cache_key:
                _set_cache(cache_key, data)

            return data

        except TimeoutError:
            log.warning(
                "AI agent request timed out after %.1fs; falling back", settings.ai_timeout_sec
            )
            break
        except Exception as exc:
            err_str = str(exc)
            is_rate_or_5xx = any(
                code in err_str for code in ("429", "500", "502", "503", "504")
            ) or isinstance(exc, ModelAPIError)

            if is_rate_or_5xx and retries < max_retries:
                retries += 1
                log.info(
                    "AI provider transient error (%s); retrying in %.1fs (%d/%d)",
                    exc,
                    backoff,
                    retries,
                    max_retries,
                )
                await asyncio.sleep(backoff)
                backoff *= 2.0
                continue

            log.warning("AI agent failed: %s; invoking rule-based fallback", exc)
            break

    # Graceful rule-based fallback
    fallback_data = fallback_fn()
    if hasattr(fallback_data, "provider_used"):
        fallback_data.provider_used = "rule_based"

    if cache_key:
        _set_cache(cache_key, fallback_data)

    return fallback_data


# ── High-Level Service Functions ────────────────────────────


async def explain_alarm(
    alarm_data: dict[str, Any],
    db: AsyncSession | None = None,
    lang: str = "ar",
) -> AlarmExplanation:
    """Diagnose an alarm and provide step-by-step guidance."""
    clean_alarm = redact_payload(alarm_data)
    cache_key = _make_cache_key(
        "alarm",
        {
            "code": clean_alarm.get("alarm_code"),
            "lang": lang,
            "val": clean_alarm.get("current_value"),
        },
    )

    prompt = (
        f"Diagnose the following farm alarm and provide guidance in preferred language: {lang}.\n"
        f"Alarm Data: {json.dumps(clean_alarm, default=str)}\n"
        f"Use tools to inspect zone state or hydraulic telemetry if relevant."
    )

    return await _run_with_retry_and_fallback(
        agent_instance=alarm_agent,
        prompt=prompt,
        deps=AIDeps(db=db),
        fallback_fn=lambda: rule_service.explain_alarm(clean_alarm, lang=lang),
        cache_key=cache_key,
    )


async def run_weather_advisor(
    forecast: WeatherForecast,
    target_date: str,
    affected_zones: list[str] | None = None,
    program_id: str | None = None,
    db: AsyncSession | None = None,
    lang: str = "ar",
) -> AdvisorSuggestion:
    """Evaluate weather thresholds and generate irrigation recommendation."""
    today_d = forecast.daily[0] if forecast.daily else None
    cache_key = _make_cache_key(
        "advisor",
        {
            "date": target_date,
            "zones": affected_zones,
            "lang": lang,
            "t_max": today_d.temp_max_c if today_d else 0.0,
            "precip": today_d.precipitation_total_mm if today_d else 0.0,
            "prob": today_d.precipitation_probability_pct if today_d else 0.0,
            "et0": today_d.et0_mm if today_d else 0.0,
        },
    )

    prompt = (
        f"Evaluate weather conditions for Algaroshy Farm on {target_date} and recommend irrigation adjustments in {lang}.\n"
        f"Target Date: {target_date}\n"
        f"Affected Zones: {affected_zones}\n"
        f"Program ID: {program_id}\n"
        f"Forecast Overview: Today max {forecast.daily[0].temp_max_c}°C, rain {forecast.daily[0].precipitation_total_mm}mm, "
        f"rain prob {forecast.daily[0].precipitation_probability_pct}%, ET0 {forecast.daily[0].et0_mm}mm.\n"
        f"Follow deterministic rules: skip if rain > 50% or precip > 2mm; extend +20% if extreme heat/high ET0."
    )

    return await _run_with_retry_and_fallback(
        agent_instance=advisor_agent,
        prompt=prompt,
        deps=AIDeps(db=db),
        fallback_fn=lambda: rule_service.weather_advisor(
            forecast=forecast,
            target_date=target_date,
            affected_zones=affected_zones,
            program_id=program_id,
            lang=lang,
        ),
        cache_key=cache_key,
    )


async def run_daily_briefing(
    date_str: str,
    cycles: list[dict[str, Any]],
    alarms: list[dict[str, Any]],
    forecast: WeatherForecast,
    db: AsyncSession | None = None,
    lang: str = "ar",
) -> DailyBriefing:
    """Synthesize daily operations briefing."""
    clean_cycles = redact_payload(cycles[:15])
    clean_alarms = redact_payload(alarms[:15])
    cache_key = _make_cache_key(
        "briefing", {"date": date_str, "cycles": len(cycles), "alarms": len(alarms), "lang": lang}
    )

    prompt = (
        f"Generate the daily operations briefing for Algaroshy Farm for date {date_str} in language: {lang}.\n"
        f"Cycles summary: {len(cycles)} cycles recorded ({json.dumps(clean_cycles, default=str)})\n"
        f"Alarms summary: {len(alarms)} alarms recorded ({json.dumps(clean_alarms, default=str)})\n"
        f"Weather summary: current {forecast.current.temperature_c}°C, condition {forecast.current.condition}."
    )

    return await _run_with_retry_and_fallback(
        agent_instance=briefing_agent,
        prompt=prompt,
        deps=AIDeps(db=db),
        fallback_fn=lambda: rule_service.daily_briefing(
            date_str=date_str,
            cycles=clean_cycles,
            alarms=clean_alarms,
            forecast=forecast,
            lang=lang,
        ),
        cache_key=cache_key,
    )


async def chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    context_zone_id: str | None = None,
    db: AsyncSession | None = None,
    lang: str = "ar",
) -> ChatResponse:
    """Process bilingual assistant query."""
    clean_msg = redact_text(message)
    cache_key = _make_cache_key("chat", {"msg": clean_msg, "lang": lang, "zone": context_zone_id})

    prompt = (
        f"Operator Query ({lang}): {clean_msg}\n"
        f"Context Zone: {context_zone_id}\n"
        f"History: {json.dumps(history or [], default=str)}\n"
        f"Use tools to look up real-time live data if needed."
    )

    return await _run_with_retry_and_fallback(
        agent_instance=chat_agent,
        prompt=prompt,
        deps=AIDeps(db=db),
        fallback_fn=lambda: rule_service.chat(clean_msg, lang=lang),
        cache_key=cache_key,
    )
