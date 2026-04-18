"""
Application configuration.

Reads from environment variables / .env file using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    farm_timezone: str = "Africa/Tripoli"
    default_language: str = "ar"

    # ── API ──────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    secret_key: str = "change-me-to-a-real-secret-key"
    access_token_expire_minutes: int = 1440

    # ── Database ─────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./farm.db"

    # ── WebSocket ────────────────────────────────────────
    ws_port: int = 8001
    ws_heartbeat_interval_sec: int = 30

    # ── AI Services ──────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_tokens: int = 2048
    gemini_temperature: float = 0.3

    # ── Weather API ──────────────────────────────────────
    weather_api_key: str = ""
    weather_api_provider: str = "openweathermap"
    weather_latitude: float = 32.8872
    weather_longitude: float = 13.1803
    weather_fetch_interval_hours: int = 3

    # ── AI Feature Toggles ───────────────────────────────
    ai_alarm_assistant_enabled: bool = True
    ai_smart_scheduling_enabled: bool = True
    ai_predictive_maintenance_enabled: bool = True
    ai_anomaly_detection_enabled: bool = True
    ai_weather_advisor_enabled: bool = True
    ai_water_optimizer_enabled: bool = True
    ai_daily_insights_enabled: bool = True
    ai_crop_vision_enabled: bool = False
    ai_voice_control_enabled: bool = False
    ai_seasonal_learning_enabled: bool = False
    ai_offline_fallback: bool = True
    ai_daily_report_time: str = "06:00"


settings = Settings()
