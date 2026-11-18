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
    farm_id: str = "farm_algaroshy"

    # ── AI Services (not implemented yet — Milestone E) ──
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    weather_api_key: str = ""
    weather_latitude: float = 32.8872
    weather_longitude: float = 13.1803

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
