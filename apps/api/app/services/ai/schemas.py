"""Pydantic schemas for AI Core & Services (Milestone E).

Strictly structured models — never parse free text.
"""

from pydantic import BaseModel, Field


class AlarmExplanation(BaseModel):
    alarm_code: str
    severity: str
    title: str
    title_ar: str
    diagnosis: str
    diagnosis_ar: str
    probable_causes: list[str] = Field(default_factory=list)
    probable_causes_ar: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    suggested_actions_ar: list[str] = Field(default_factory=list)
    safety_critical: bool = False
    confidence: float = 0.95
    provider_used: str = "rule_based"


class AdvisorSuggestion(BaseModel):
    action: str  # "skip" | "extend" | "reduce" | "delay" | "none"
    target_date: str  # YYYY-MM-DD (farm local date)
    affected_zone_ids: list[str] = Field(default_factory=list)
    program_id: str | None = None
    duration_factor: float = 1.0  # 0.0 for skip, 1.2 for extend 20%, 0.8 for reduce 20%
    title: str
    title_ar: str
    reasoning: str
    reasoning_ar: str
    confidence: float = 0.95
    provider_used: str = "rule_based"


class DailyBriefing(BaseModel):
    date: str  # YYYY-MM-DD
    title: str
    title_ar: str
    summary: str
    summary_ar: str
    weather_summary: str
    weather_summary_ar: str
    irrigation_overview: str
    irrigation_overview_ar: str
    alarms_overview: str
    alarms_overview_ar: str
    recommendations: list[str] = Field(default_factory=list)
    recommendations_ar: list[str] = Field(default_factory=list)
    provider_used: str = "rule_based"


class ChatResponse(BaseModel):
    reply: str
    reply_ar: str
    references: list[str] = Field(default_factory=list)
    provider_used: str = "rule_based"


# ── Request / Response models for API endpoints ──────────────


class AlarmExplainRequest(BaseModel):
    alarm_id: str | None = None
    alarm_code: str | None = None
    language: str = "ar"


class ChatRequest(BaseModel):
    message: str
    language: str = "ar"
    context_zone_id: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class SuggestionActionRequest(BaseModel):
    notes: str | None = None


class AISettingsResponse(BaseModel):
    primary_provider: str = "apinex"
    fallback_provider: str = "gemini"
    apinex_base_url: str
    apinex_model: str
    gemini_model: str
    offline_fallback: bool
    timeout_sec: float
    token_budget: int
    daily_briefing_time: str
    weather_provider: str
    weather_coordinates: dict[str, float]
    weather_timezone: str
