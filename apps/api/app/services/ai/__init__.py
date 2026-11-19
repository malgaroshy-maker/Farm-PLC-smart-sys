"""AI Core & Services Package (Milestone E).

Provides:
  - Pydantic AI integration with FallbackModel (APInex -> Gemini -> Rule-based)
  - Strict payload redaction
  - Weather-aware irrigation advisor with one-day scheduler overrides
  - Daily farm operations briefing at 06:00 farm time
  - Read-only tools for live context
"""

from app.services.ai.advisor import (
    approve_suggestion,
    evaluate_weather_advisor,
    reject_suggestion,
)
from app.services.ai.agent import (
    advisor_agent,
    alarm_agent,
    briefing_agent,
    chat,
    chat_agent,
    clear_ai_cache,
    explain_alarm,
    run_daily_briefing,
    run_weather_advisor,
)
from app.services.ai.briefing import (
    check_scheduled_briefing,
    get_or_generate_daily_briefing,
)
from app.services.ai.providers import (
    build_fallback_chain,
    fetch_apinex_models,
    get_fallback_model,
    get_primary_model,
    identify_provider_label,
)
from app.services.ai.redaction import redact_payload, redact_text
from app.services.ai.rules import RuleBasedService, rule_service
from app.services.ai.schemas import (
    AdvisorSuggestion,
    AISettingsResponse,
    AlarmExplainRequest,
    AlarmExplanation,
    ChatRequest,
    ChatResponse,
    DailyBriefing,
    SuggestionActionRequest,
)
from app.services.ai.tools import AI_TOOLS, AIDeps

__all__ = [
    "alarm_agent",
    "advisor_agent",
    "briefing_agent",
    "chat_agent",
    "clear_ai_cache",
    "explain_alarm",
    "run_weather_advisor",
    "run_daily_briefing",
    "chat",
    "evaluate_weather_advisor",
    "approve_suggestion",
    "reject_suggestion",
    "get_or_generate_daily_briefing",
    "check_scheduled_briefing",
    "build_fallback_chain",
    "fetch_apinex_models",
    "get_primary_model",
    "get_fallback_model",
    "identify_provider_label",
    "redact_payload",
    "redact_text",
    "rule_service",
    "RuleBasedService",
    "AlarmExplanation",
    "AdvisorSuggestion",
    "DailyBriefing",
    "ChatResponse",
    "AlarmExplainRequest",
    "ChatRequest",
    "SuggestionActionRequest",
    "AISettingsResponse",
    "AI_TOOLS",
    "AIDeps",
]
