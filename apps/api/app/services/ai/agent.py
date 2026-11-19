"""Pydantic AI Agents Core (Milestone E).

Implements:
  - Pydantic AI Agents with FallbackModel (APInex -> Gemini -> Rule-based)
  - Structured output models (AlarmExplanation, AdvisorSuggestion, DailyBriefing, ChatResponse)
  - Read-only tools for live context (concurrency-safe with session_factory)
  - Timeouts (45s explain/chat, 90s advisor/briefing), retry/backoff on 429/5xx, UsageLimits(request_limit=5)
  - Strict payload redaction before sending
  - Dynamic farm context block querying Zone table
  - Fallback visibility & last 20 call recorder
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import utcnow
from app.database import async_session_factory
from app.models.ai import AISettings
from app.models.zone import Zone
from app.services.ai.providers import (
    build_fallback_chain,
    get_apinex_fallback_model,
    get_fallback_model,
    get_primary_model,
    identify_provider_label,
)
from app.services.ai.purity import check_response_purity
from app.services.ai.redaction import redact_payload, redact_text
from app.services.ai.rules import rule_service
from app.services.ai.schemas import (
    AdvisorSuggestion,
    AlarmExplanation,
    ChatResponse,
    DailyBriefing,
)
from app.services.ai.tools import AI_TOOLS, AIDeps
from app.services.live_state import load_snapshots
from app.services.weather import WeatherForecast

log = logging.getLogger(__name__)

# Request Cache: (cache_key -> (timestamp, data))
_REQUEST_CACHE: dict[str, tuple[datetime, Any]] = {}
CACHE_TTL_SEC = 60.0

# In-memory recent calls ring buffer (last 20 calls)
_RECENT_CALLS: deque[dict[str, Any]] = deque(maxlen=20)
_LAST_PRIMARY_FAILED: bool = False


def classify_failure(error: str | None) -> str:
    """Short machine-readable reason shown to admins when rule-based answers are used."""
    e = (error or "").lower()
    if not e:
        return "unknown"
    if "timed out" in e or "timeout" in e:
        return "timeout"
    if "tool" in e and "retr" in e:
        return "tool_error"
    if "validation" in e:
        return "invalid_output"
    if any(c in e for c in ("400", "401", "402", "403", "404", "429", "500", "502", "503", "504")):
        return "provider_error"
    return "error"


def record_ai_call(
    feature: str,
    provider: str,
    model: str,
    latency_ms: float,
    fallback_reason: str | None = None,
) -> None:
    """Record an AI invocation for visibility and health reporting."""
    global _LAST_PRIMARY_FAILED
    call_id = f"call_{uuid.uuid4().hex[:8]}"
    now_iso = clock.farm_now().isoformat()

    if fallback_reason is not None and provider != "apinex":
        _LAST_PRIMARY_FAILED = True
    elif provider == "apinex":
        _LAST_PRIMARY_FAILED = False

    _RECENT_CALLS.appendleft(
        {
            "id": call_id,
            "timestamp": now_iso,
            "feature": feature,
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 1),
            "fallback_reason": fallback_reason,
        }
    )


def get_recent_ai_calls() -> list[dict[str, Any]]:
    """Return the last 20 recorded AI calls."""
    return list(_RECENT_CALLS)


def is_primary_degraded() -> bool:
    """Check if the primary AI provider is currently degraded."""
    if _LAST_PRIMARY_FAILED:
        return True
    if _RECENT_CALLS:
        latest = _RECENT_CALLS[0]
        if latest.get("fallback_reason") is not None and latest.get("provider") != "apinex":
            return True
    return False


def reset_call_history() -> None:
    """Reset call history and health status (primarily for tests)."""
    global _LAST_PRIMARY_FAILED
    _RECENT_CALLS.clear()
    _LAST_PRIMARY_FAILED = False


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


# ── Dynamic Farm Context ─────────────────────────────────────


async def build_farm_context_block(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> str:
    """Dynamically query Zone table to build farm context block (zone names, crops, area, state)."""
    factory = session_factory or async_session_factory
    try:
        async with factory() as db:
            stmt = select(Zone).where(Zone.enabled.is_(True)).order_by(Zone.code)
            res = await db.execute(stmt)
            zones = list(res.scalars().all())
            snapshots = await load_snapshots(db)

            if not zones:
                return "Farm Context: No active zones configured."

            lines = ["Active Farm Zones & Crops:"]
            for z in zones:
                snap = snapshots.get(f"zone_{z.id}") or snapshots.get(f"zone:{z.id}")
                live_data = (
                    snap.state
                    if snap and hasattr(snap, "state")
                    else (snap.data if snap and hasattr(snap, "data") else {})
                )
                state = live_data.get("state", "idle")
                lines.append(
                    f"- Zone {z.code} ({z.name} / {z.name_ar or z.name}): Crop={z.crop_type}, Area={z.area_ha or 0.0}ha, State={state}"
                )
            return "\n".join(lines)
    except Exception as exc:
        log.warning("Could not build farm context block: %s", exc)
        return "Farm Context: Unavailable"


# ── Dynamic Settings & Models ────────────────────────────────


async def get_db_settings_and_model(
    feature: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> tuple[AISettings | None, Model | None]:
    """Load persistent AI settings from DB and construct feature-specific model if configured."""
    factory = session_factory or async_session_factory
    try:
        async with factory() as db:
            stmt = select(AISettings).where(AISettings.id == "default")
            res = await db.execute(stmt)
            s = res.scalar_one_or_none()
            if not s:
                return None, None

            if not s.global_enabled:
                return s, None

            # Determine feature model override
            feature_model = None
            if feature == "alarm" and s.model_alarm:
                feature_model = s.model_alarm
            elif feature == "advisor" and s.model_advisor:
                feature_model = s.model_advisor
            elif feature == "briefing" and s.model_briefing:
                feature_model = s.model_briefing
            elif feature == "chat" and s.model_chat:
                feature_model = s.model_chat

            p_model = get_primary_model(
                model_name=feature_model or s.apinex_model,
                base_url=s.apinex_base_url,
            )
            s_model = get_apinex_fallback_model(model_name=s.apinex_fallback_model)
            f_model = get_fallback_model(model_name=s.gemini_model)
            chain = build_fallback_chain(
                primary_model=p_model,
                secondary_model=s_model,
                fallback_model=f_model,
            )
            db.expunge(s)
            return s, chain
    except Exception as exc:
        log.warning("Failed to load DB AI settings: %s", exc)
        return None, None


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
Answer operator queries about pumps, zones, crops, alarms, and weather using the provided live farm context.
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
    retries=2,
)

advisor_agent = Agent(
    model=build_fallback_chain(),
    output_type=AdvisorSuggestion,
    system_prompt=ADVISOR_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
    retries=2,
)

briefing_agent = Agent(
    model=build_fallback_chain(),
    output_type=DailyBriefing,
    system_prompt=BRIEFING_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
    retries=2,
)

chat_agent = Agent(
    model=build_fallback_chain(),
    output_type=ChatResponse,
    system_prompt=CHAT_SYSTEM_PROMPT,
    tools=AI_TOOLS,
    deps_type=AIDeps,
    retries=2,
)


# ── Robust Execution Helper ─────────────────────────────────


async def _run_with_retry_and_fallback(
    agent_instance: Agent,
    prompt: str,
    deps: AIDeps,
    fallback_fn: Callable[[], Any],
    cache_key: str | None = None,
    timeout_sec: float | None = None,
    feature_name: str = "ai_feature",
    override_model: Model | None = None,
    global_enabled: bool = True,
) -> Any:
    """Execute Pydantic AI agent with timeouts, exponential retry on 429/5xx, and rule fallback."""
    if not global_enabled:
        fallback_data = fallback_fn()
        if hasattr(fallback_data, "provider_used"):
            fallback_data.provider_used = "rule_based"
        record_ai_call(
            feature=feature_name,
            provider="rule_based",
            model="offline_rules",
            latency_ms=0.0,
            fallback_reason="Global AI disabled",
        )
        return fallback_data

    if cache_key:
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached

    # Strict Redaction before external dispatch
    safe_prompt = redact_text(prompt)

    retries = 0
    max_retries = max(0, settings.ai_max_retries)
    backoff = 0.5
    eff_timeout = timeout_sec or settings.ai_timeout_sec
    last_error: str | None = None
    tried_second_model = False
    start_time = time.monotonic()

    while True:
        try:
            # Enforce timeout and request limits
            result = await asyncio.wait_for(
                agent_instance.run(
                    safe_prompt,
                    deps=deps,
                    model=override_model,
                    usage_limits=UsageLimits(request_limit=8),
                ),
                timeout=eff_timeout,
            )
            latency_ms = (time.monotonic() - start_time) * 1000
            data = result.output

            # Arabic purity guard: audit Arabic text for Hangul, CJK, Kana, Cyrillic, and English words
            purity = check_response_purity(data)
            fallback_reason: str | None = None

            if not purity.is_pure:
                log.warning(
                    "Arabic purity guard triggered (%d foreign chars, %d English words: %s); retrying with fallback model",
                    purity.foreign_char_count,
                    purity.english_word_count,
                    purity.violating_words,
                )
                try:
                    cleaner_model = get_apinex_fallback_model()
                    clean_result = await asyncio.wait_for(
                        agent_instance.run(
                            safe_prompt,
                            deps=deps,
                            model=cleaner_model,
                            usage_limits=UsageLimits(request_limit=8),
                        ),
                        timeout=eff_timeout,
                    )
                    clean_data = clean_result.output
                    clean_purity = check_response_purity(clean_data)
                    fallback_reason = "language_purity"
                    # If retry is cleaner, select it
                    if clean_purity.total_violations < purity.total_violations:
                        data = clean_data
                        result = clean_result
                except Exception as retry_exc:
                    log.info("Purity retry error (%s); keeping primary output", retry_exc)
                    fallback_reason = "language_purity"

            # Identify provider label & model name
            provider_label = identify_provider_label(result.response)
            model_name = getattr(result.response, "model_name", None) or "llm_agent"

            if hasattr(data, "provider_used"):
                data.provider_used = provider_label
            if hasattr(data, "model_used"):
                data.model_used = str(model_name)
            if hasattr(data, "fallback_reason"):
                # Set by us, never by the model (it may fill the field with e.g. "none").
                data.fallback_reason = fallback_reason

            record_ai_call(
                feature=feature_name,
                provider=provider_label,
                model=str(model_name),
                latency_ms=latency_ms,
                fallback_reason=fallback_reason,
            )

            if cache_key:
                _set_cache(cache_key, data)

            return data

        except TimeoutError:
            latency_ms = (time.monotonic() - start_time) * 1000
            last_error = f"Timed out after {eff_timeout:.1f}s"
            log.warning("AI agent request timed out after %.1fs; falling back", eff_timeout)
            break
        except Exception as exc:
            err_str = str(exc)
            last_error = err_str
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

            # Non-transient failure (tool retries exhausted, invalid output, provider
            # refused): give the second APInex model one chance before rule-based.
            if not tried_second_model:
                tried_second_model = True
                try:
                    override_model = get_apinex_fallback_model()
                    log.warning("AI agent failed (%s); retrying once with fallback model", exc)
                    continue
                except Exception:  # noqa: BLE001
                    pass
            log.warning("AI agent failed: %s; invoking rule-based fallback", exc)
            break

    # Graceful rule-based fallback
    latency_ms = (time.monotonic() - start_time) * 1000
    fallback_data = fallback_fn()
    if hasattr(fallback_data, "provider_used"):
        fallback_data.provider_used = "rule_based"
    if hasattr(fallback_data, "model_used"):
        fallback_data.model_used = "offline_rules"
    reason = classify_failure(last_error)
    if hasattr(fallback_data, "fallback_reason"):
        fallback_data.fallback_reason = reason

    record_ai_call(
        feature=feature_name,
        provider="rule_based",
        model="offline_rules",
        latency_ms=latency_ms,
        fallback_reason=f"{reason}: {(last_error or 'unknown')[:160]}",
    )

    if cache_key:
        _set_cache(cache_key, fallback_data)

    return fallback_data


# ── High-Level Service Functions ────────────────────────────


async def explain_alarm(
    alarm_data: dict[str, Any],
    db: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    lang: str = "ar",
) -> AlarmExplanation:
    """Diagnose an alarm and provide step-by-step guidance."""
    factory = session_factory or async_session_factory
    ai_settings_rec, dynamic_model = await get_db_settings_and_model("alarm", factory)
    global_enabled = ai_settings_rec.global_enabled if ai_settings_rec else True

    clean_alarm = redact_payload(alarm_data)
    cache_key = _make_cache_key(
        "alarm",
        {
            "code": clean_alarm.get("alarm_code"),
            "lang": lang,
            "val": clean_alarm.get("current_value"),
        },
    )

    farm_context = await build_farm_context_block(factory)
    prompt = (
        f"Diagnose the following farm alarm and provide guidance in preferred language: {lang}.\n"
        f"Alarm Data: {json.dumps(clean_alarm, default=str)}\n"
        f"{farm_context}\n"
        f"Use tools to inspect zone state or hydraulic telemetry if relevant."
    )

    timeout = ai_settings_rec.timeout_sec if ai_settings_rec else settings.ai_timeout_sec

    return await _run_with_retry_and_fallback(
        agent_instance=alarm_agent,
        prompt=prompt,
        deps=AIDeps(session_factory=factory),
        fallback_fn=lambda: rule_service.explain_alarm(clean_alarm, lang=lang),
        cache_key=cache_key,
        timeout_sec=timeout or 45.0,
        feature_name="explain_alarm",
        override_model=dynamic_model,
        global_enabled=global_enabled,
    )


async def run_weather_advisor(
    forecast: WeatherForecast,
    target_date: str,
    affected_zones: list[str] | None = None,
    program_id: str | None = None,
    db: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    lang: str = "ar",
) -> AdvisorSuggestion:
    """Evaluate weather thresholds and generate irrigation recommendation."""
    factory = session_factory or async_session_factory
    ai_settings_rec, dynamic_model = await get_db_settings_and_model("advisor", factory)
    global_enabled = ai_settings_rec.global_enabled if ai_settings_rec else True

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

    farm_context = await build_farm_context_block(factory)
    prompt = (
        f"Evaluate weather conditions for Algaroshy Farm on {target_date} and recommend irrigation adjustments in {lang}.\n"
        f"Target Date: {target_date}\n"
        f"Affected Zones: {affected_zones}\n"
        f"Program ID: {program_id}\n"
        f"Weather Summary: TempMax={today_d.temp_max_c if today_d else 'N/A'}°C, Precip={today_d.precipitation_total_mm if today_d else 'N/A'}mm, ET0={today_d.et0_mm if today_d else 'N/A'}mm\n"
        f"{farm_context}\n"
        f"Follow deterministic rules strictly. Output bilingual justification."
    )

    timeout = (
        ai_settings_rec.advisor_timeout_sec if ai_settings_rec else settings.ai_advisor_timeout_sec
    )

    return await _run_with_retry_and_fallback(
        agent_instance=advisor_agent,
        prompt=prompt,
        deps=AIDeps(session_factory=factory),
        fallback_fn=lambda: rule_service.weather_advisor(
            forecast=forecast,
            target_date=target_date,
            affected_zones=affected_zones,
            program_id=program_id,
            lang=lang,
        ),
        cache_key=cache_key,
        timeout_sec=timeout or 90.0,
        feature_name="advisor",
        override_model=dynamic_model,
        global_enabled=global_enabled,
    )


async def run_daily_briefing(
    date_str: str,
    forecast: WeatherForecast | None = None,
    cycles: Any | None = None,
    alarms: Any | None = None,
    cycles_summary: dict[str, Any] | None = None,
    alarms_summary: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    lang: str = "ar",
) -> DailyBriefing:
    """Generate comprehensive farm operations morning briefing."""
    factory = session_factory or async_session_factory
    ai_settings_rec, dynamic_model = await get_db_settings_and_model("briefing", factory)
    global_enabled = ai_settings_rec.global_enabled if ai_settings_rec else True

    cycles_data = cycles if cycles is not None else cycles_summary
    alarms_data = alarms if alarms is not None else alarms_summary

    cache_key = _make_cache_key("briefing", {"date": date_str, "lang": lang})

    farm_context = await build_farm_context_block(factory)
    prompt = (
        f"Synthesize the daily farm operations briefing for {date_str} in {lang}.\n"
        f"Past 24h Cycles: {json.dumps(cycles_data or {}, default=str)}\n"
        f"Alarms Summary: {json.dumps(alarms_data or {}, default=str)}\n"
        f"{farm_context}\n"
        f"Produce bilingual executive summary, water delivered, active warnings, and operations plan."
    )

    timeout = (
        ai_settings_rec.advisor_timeout_sec if ai_settings_rec else settings.ai_advisor_timeout_sec
    )

    return await _run_with_retry_and_fallback(
        agent_instance=briefing_agent,
        prompt=prompt,
        deps=AIDeps(session_factory=factory),
        fallback_fn=lambda: rule_service.daily_briefing(
            date_str=date_str,
            forecast=forecast,
            cycles=cycles_data if isinstance(cycles_data, list) else None,
            alarms=alarms_data if isinstance(alarms_data, list) else None,
            cycles_summary=cycles_data,
            alarms_summary=alarms_data,
            lang=lang,
        ),
        cache_key=cache_key,
        timeout_sec=timeout or 90.0,
        feature_name="briefing",
        override_model=dynamic_model,
        global_enabled=global_enabled,
    )


async def chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    context_zone_id: str | None = None,
    db: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    lang: str = "ar",
) -> ChatResponse:
    """Conversational farm assistant answering operator questions."""
    factory = session_factory or async_session_factory
    ai_settings_rec, dynamic_model = await get_db_settings_and_model("chat", factory)
    global_enabled = ai_settings_rec.global_enabled if ai_settings_rec else True

    clean_message = redact_text(message)
    farm_context = await build_farm_context_block(factory)
    prompt = (
        f"User Message: {clean_message}\n"
        f"Preferred Language: {lang}\n"
        f"Context Zone: {context_zone_id or 'all'}\n"
        f"Recent History: {json.dumps(history or [], default=str)}\n"
        f"{farm_context}\n"
        f"Inspect live farm context using tools if necessary and answer concisely and safely."
    )

    timeout = ai_settings_rec.timeout_sec if ai_settings_rec else settings.ai_timeout_sec

    return await _run_with_retry_and_fallback(
        agent_instance=chat_agent,
        prompt=prompt,
        deps=AIDeps(session_factory=factory),
        fallback_fn=lambda: rule_service.chat(clean_message, lang=lang),
        timeout_sec=timeout or 45.0,
        feature_name="chat",
        override_model=dynamic_model,
        global_enabled=global_enabled,
    )
