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
    model_used: str = ""


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
    model_used: str = ""


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
    model_used: str = ""


class ChatResponse(BaseModel):
    reply: str = ""
    reply_ar: str = ""
    message: str | None = None
    references: list[str] = Field(default_factory=list)
    provider_used: str = "rule_based"
    model_used: str = ""


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


class AICallRecord(BaseModel):
    id: str
    timestamp: str
    feature: str
    provider: str
    model: str
    latency_ms: float
    fallback_reason: str | None = None


class AISettingsResponse(BaseModel):
    global_enabled: bool = True
    primary_provider: str = "apinex"
    fallback_provider: str = "gemini"
    apinex_base_url: str
    apinex_model: str
    apinex_fallback_model: str = "free/muse-spark-1.3"
    gemini_model: str
    model_alarm: str | None = None
    model_advisor: str | None = None
    model_briefing: str | None = None
    model_chat: str | None = None
    alarm_assistant_enabled: bool = True
    smart_scheduling_enabled: bool = True
    predictive_maintenance_enabled: bool = True
    anomaly_detection_enabled: bool = True
    weather_advisor_enabled: bool = True
    water_optimizer_enabled: bool = True
    daily_insights_enabled: bool = True
    offline_fallback: bool
    timeout_sec: float
    advisor_timeout_sec: float = 90.0
    token_budget: int
    daily_briefing_time: str
    weather_provider: str
    weather_coordinates: dict[str, float]
    weather_timezone: str
    key_status: dict[str, bool] = Field(default_factory=dict)
    recent_calls: list[AICallRecord] = Field(default_factory=list)


class AISettingsUpdateRequest(BaseModel):
    global_enabled: bool | None = None
    primary_provider: str | None = None
    fallback_provider: str | None = None
    apinex_base_url: str | None = None
    apinex_model: str | None = None
    apinex_fallback_model: str | None = None
    gemini_model: str | None = None
    model_alarm: str | None = None
    model_advisor: str | None = None
    model_briefing: str | None = None
    model_chat: str | None = None
    alarm_assistant_enabled: bool | None = None
    smart_scheduling_enabled: bool | None = None
    predictive_maintenance_enabled: bool | None = None
    anomaly_detection_enabled: bool | None = None
    weather_advisor_enabled: bool | None = None
    water_optimizer_enabled: bool | None = None
    daily_insights_enabled: bool | None = None
    offline_fallback: bool | None = None
    timeout_sec: float | None = None
    advisor_timeout_sec: float | None = None
    token_budget: int | None = None
    daily_briefing_time: str | None = None
