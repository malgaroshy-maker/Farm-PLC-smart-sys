"""AI-related database models — suggestions, anomalies, weather cache, insights."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdentityMixin, TimestampMixin


class AISuggestion(Base, IdentityMixin):
    """AI-generated suggestions (scheduling, maintenance, optimization)."""

    __tablename__ = "ai_suggestions"

    feature: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)
    reasoning_ar: Mapped[str | None] = mapped_column(Text)
    action_payload_json: Mapped[str | None] = mapped_column(Text)
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.id"))
    device_id: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_by: Mapped[str | None] = mapped_column(String(64))


class DetectedAnomaly(Base, IdentityMixin):
    """Anomalies detected by the AI anomaly engine."""

    __tablename__ = "detected_anomalies"

    anomaly_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), default="warning")
    zone_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("zones.id"))
    device_id: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_explanation_ar: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by: Mapped[str | None] = mapped_column(String(64))


class WeatherCache(Base):
    """Cached weather data from external API."""

    __tablename__ = "weather_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float)
    wind_direction: Mapped[str | None] = mapped_column(String(10))
    precipitation_mm: Mapped[float | None] = mapped_column(Float)
    precipitation_probability_pct: Mapped[float | None] = mapped_column(Float)
    uv_index: Mapped[float | None] = mapped_column(Float)
    condition: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(200))
    description_ar: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(30), default="openweathermap")
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False)
    forecast_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WeatherAdvisory(Base, IdentityMixin):
    """Weather-based irrigation advisories."""

    __tablename__ = "weather_advisories"

    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    affected_zone_ids_json: Mapped[str | None] = mapped_column(Text)  # JSON array
    message: Mapped[str | None] = mapped_column(Text)
    message_ar: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIInsight(Base, IdentityMixin):
    """AI-generated insight reports (daily, weekly summaries)."""

    __tablename__ = "ai_insights"

    insight_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(5), default="ar")
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    title: Mapped[str | None] = mapped_column(String(200))
    title_ar: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    summary_ar: Mapped[str | None] = mapped_column(Text)
    sections_json: Mapped[str | None] = mapped_column(Text)  # JSON array of InsightSection
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(20), default="gemini")


class MaintenancePrediction(Base, IdentityMixin):
    """Predictive maintenance predictions for equipment."""

    __tablename__ = "maintenance_predictions"

    device_type: Mapped[str] = mapped_column(String(20), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_name: Mapped[str | None] = mapped_column(String(100))
    device_name_ar: Mapped[str | None] = mapped_column(String(100))
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    health_band: Mapped[str] = mapped_column(String(20), default="excellent")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_days_to_failure: Mapped[int | None] = mapped_column(Integer)
    trend_direction: Mapped[str] = mapped_column(String(15), default="stable")
    metrics_json: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    recommendation_ar: Mapped[str | None] = mapped_column(Text)
    last_analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
