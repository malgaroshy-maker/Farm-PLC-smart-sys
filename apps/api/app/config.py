"""
Application configuration.

Reads from environment variables / .env file using pydantic-settings.
The API looks for `.env` in its own folder first, then at the repo root.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-me-to-a-real-secret-key"
DEFAULT_SIMULATOR_TOKEN = "dev-simulator-token"


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = False
    farm_timezone: str = "Africa/Tripoli"
    default_language: str = "ar"
    deployment_mode: str = "simulation"  # simulation | local_pilot | production_hybrid
    controller_mode: str = "simulator"  # simulator | plc

    # ── API ──────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    secret_key: str = DEFAULT_SECRET
    access_token_expire_minutes: int = 1440
    # Comma-separated list. The Vite dev server proxies /api and /ws, so the
    # browser normally talks same-origin and CORS only matters for direct access.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Auth bootstrap ───────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = ""  # empty → seed generates one and prints it once
    # Shared secret the simulator / PLC bridge uses to call the API.
    simulator_token: str = DEFAULT_SIMULATOR_TOKEN

    # ── Database ─────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./farm.db"

    # ── Live state / commands ────────────────────────────
    state_stale_after_sec: float = 5.0
    comm_lost_after_sec: float = 30.0
    command_timeout_sec: float = 15.0  # not picked up by the controller
    command_execution_timeout_sec: float = 180.0  # accepted but never finished
    max_concurrent_zones: int = 1  # dual-zone disabled until commissioning (PLC_CONTROL_LOGIC §7)
    tank_critical_pct: float = 10.0
    tank_warning_pct: float = 25.0
    monitor_interval_sec: float = 1.0

    # ── Alarms & telemetry ───────────────────────────────
    alarm_debounce_sec: float = 10.0  # derived pressure warnings
    tank_warning_debounce_sec: float = 5.0
    repeated_fault_threshold: int = 3  # ALM-036: major faults per zone per 24 h
    telemetry_interval_sec: float = 10.0
    telemetry_retention_days: int = 7
    # Older samples are thinned to one per bucket so long charts stay fast.
    telemetry_downsample_after_hours: int = 48
    telemetry_downsample_bucket_sec: int = 300
    # Optional rotating log file (empty = console only), e.g. "logs/api.log".
    log_file: str = ""
    log_file_max_mb: int = 5
    log_file_backups: int = 5
    farm_id: str = "farm_algaroshy"

    # ── AI Services (Milestone E) ────────────────────────
    # Primary: APInex (OpenAI-compatible)
    apinex_base_url: str = "https://api.apinex.bond/v1"
    apinex_api_key: str = ""
    apinex_model: str = "free/deepseek-v4-pro-0813"
    apinex_fallback_model: str = "free/minimax-m3.1-flash"

    # Fallback: Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # AI General & Resilience
    ai_timeout_sec: float = 45.0
    ai_advisor_timeout_sec: float = 90.0
    ai_max_retries: int = 2
    ai_token_budget: int = 2048
    ai_offline_fallback: bool = True
    ai_daily_briefing_time: str = "06:00"

    # Weather (Open-Meteo)
    weather_api_provider: str = "open-meteo"
    weather_api_key: str = ""
    weather_latitude: float = 32.516250
    weather_longitude: float = 14.070361
    weather_timezone: str = "Africa/Tripoli"
    weather_cache_ttl_sec: int = 10800  # 3 hours (3h cache)

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # Accept the common sync URL and upgrade it to the async driver.
        if v.startswith("sqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def check_production_safety(self) -> None:
        """Refuse to run in production with development secrets."""
        if not self.is_production:
            return
        problems = []
        if self.secret_key == DEFAULT_SECRET:
            problems.append("SECRET_KEY")
        if self.simulator_token == DEFAULT_SIMULATOR_TOKEN:
            problems.append("SIMULATOR_TOKEN")
        if problems:
            raise RuntimeError(f"Set real values for {', '.join(problems)} in production.")


settings = Settings()
