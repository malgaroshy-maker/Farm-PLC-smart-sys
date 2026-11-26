"""Open-Meteo Weather Service (Milestone E).

Fetches live forecast data for Algaroshy Farm (32.516250, 14.070361, Africa/Tripoli).
Features:
  - 3-hour caching (in-memory + DB persistence)
  - Resilient fallback on network/API failure
  - WMO weather code translation to bilingual Arabic/English strings
  - FAO-56 Penman-Monteith Evapotranspiration (ET0) tracking
"""

import json
import logging
from datetime import date, datetime
from math import isfinite
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc
from app.models.ai import WeatherCache

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_VALIDATED_CACHE = "validated_provider_fields"

_CURRENT_FIELDS = {
    "temperature_c": "temperature_2m",
    "humidity_pct": "relative_humidity_2m",
    "wind_speed_kmh": "wind_speed_10m",
    "wind_direction": "wind_direction_10m",
    "precipitation_mm": "precipitation",
    "cloud_cover_pct": "cloud_cover",
}
_HOURLY_FIELDS = {
    **_CURRENT_FIELDS,
    "precipitation_probability_pct": "precipitation_probability",
    "et0_mm": "et0_fao_evapotranspiration",
}
_DAILY_FIELDS = {
    "temp_min_c": "temperature_2m_min",
    "temp_max_c": "temperature_2m_max",
    "precipitation_total_mm": "precipitation_sum",
    "precipitation_probability_pct": "precipitation_probability_max",
    "et0_mm": "et0_fao_evapotranspiration",
}

# WMO Weather interpretation codes (WW)
WMO_CODES: dict[int, dict[str, str]] = {
    0: {"condition": "clear", "en": "Clear sky", "ar": "سماء صافية"},
    1: {"condition": "clear", "en": "Mainly clear", "ar": "صافٍ غالباً"},
    2: {"condition": "cloudy", "en": "Partly cloudy", "ar": "غائم جزئياً"},
    3: {"condition": "cloudy", "en": "Overcast", "ar": "غائم تماماً"},
    45: {"condition": "fog", "en": "Fog", "ar": "ضباب"},
    48: {"condition": "fog", "en": "Depositing rime fog", "ar": "ضباب جليدي"},
    51: {"condition": "rain_light", "en": "Light drizzle", "ar": "رذاذ خفيف"},
    53: {"condition": "rain_light", "en": "Moderate drizzle", "ar": "رذاذ معتدل"},
    55: {"condition": "rain_light", "en": "Dense drizzle", "ar": "رذاذ كثيف"},
    61: {"condition": "rain_light", "en": "Slight rain", "ar": "مطر خفيف"},
    63: {"condition": "rain_moderate", "en": "Moderate rain", "ar": "مطر معتدل"},
    65: {"condition": "rain_heavy", "en": "Heavy rain", "ar": "مطر غزير"},
    71: {"condition": "snow", "en": "Slight snow fall", "ar": "تساقط ثلوج خفيف"},
    73: {"condition": "snow", "en": "Moderate snow fall", "ar": "تساقط ثلوج معتدل"},
    75: {"condition": "snow", "en": "Heavy snow fall", "ar": "تساقط ثلوج كثيف"},
    80: {"condition": "rain_light", "en": "Slight rain showers", "ar": "زخات مطر خفيفة"},
    81: {"condition": "rain_moderate", "en": "Moderate rain showers", "ar": "زخات مطر معتدلة"},
    82: {"condition": "rain_heavy", "en": "Violent rain showers", "ar": "زخات مطر عنيفة"},
    95: {"condition": "thunderstorm", "en": "Thunderstorm", "ar": "عاصفة رعدية"},
    96: {
        "condition": "thunderstorm",
        "en": "Thunderstorm with slight hail",
        "ar": "عاصفة رعدية مع بَرَد خفيف",
    },
    99: {
        "condition": "thunderstorm",
        "en": "Thunderstorm with heavy hail",
        "ar": "عاصفة رعدية مع بَرَد كثيف",
    },
}


def _interpret_wmo(code: int | None) -> dict[str, str]:
    if code is not None and code in WMO_CODES:
        return WMO_CODES[code]
    return {"condition": "unknown", "en": "Unknown conditions", "ar": "طقس غير معروف"}


def _observations(raw: dict, fields: dict[str, str], index: int | None = None) -> dict | None:
    values = {}
    for field, source in fields.items():
        value = raw.get(source)
        if index is not None:
            value = value[index] if isinstance(value, list) and index < len(value) else None
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
            return None
        values[field] = str(value) if field == "wind_direction" else float(value)
    return values


class WeatherData(BaseModel):
    timestamp: str
    temperature_c: float
    humidity_pct: float
    wind_speed_kmh: float
    wind_direction: str = "N"
    precipitation_mm: float = 0.0
    precipitation_probability_pct: float | None = None
    cloud_cover_pct: float = 0.0
    uv_index: float | None = None
    et0_mm: float | None = None
    condition: str = "clear"
    description: str = "Clear"
    description_ar: str = "صافٍ"


class WeatherDaySummary(BaseModel):
    date: str  # YYYY-MM-DD
    temp_min_c: float
    temp_max_c: float
    humidity_avg_pct: float | None = None
    precipitation_total_mm: float = 0.0
    precipitation_probability_pct: float = 0.0
    et0_mm: float = 0.0
    condition: str = "clear"
    description: str = "Clear"
    description_ar: str = "صافٍ"


class WeatherForecast(BaseModel):
    current: WeatherData
    hourly: list[WeatherData] = Field(default_factory=list)
    daily: list[WeatherDaySummary] = Field(default_factory=list)
    last_fetched_at: str
    source: str = "open-meteo"
    cached: bool = False


def is_usable_forecast(forecast: WeatherForecast | None) -> bool:
    if not forecast or forecast.source == "offline_fallback":
        return False
    try:
        age = as_utc(clock.farm_now()) - as_utc(datetime.fromisoformat(forecast.last_fetched_at))
    except ValueError:
        return False
    return 0 <= age.total_seconds() <= settings.weather_cache_ttl_sec


class WeatherService:
    def __init__(self) -> None:
        self._cached_forecast: WeatherForecast | None = None
        self._cache_time: datetime | None = None
        self._last_error: str | None = None
        self._last_success_time: datetime | None = None

    def reset_cache(self) -> None:
        """Clear in-memory cache (primarily for tests)."""
        self._cached_forecast = None
        self._cache_time = None
        self._last_error = None
        self._last_success_time = None

    def is_cache_valid(self) -> bool:
        return is_usable_forecast(self._cached_forecast)

    async def get_forecast(
        self, db: AsyncSession | None = None, force_refresh: bool = False
    ) -> WeatherForecast | None:
        """Retrieve 7-day weather forecast, with 3h caching and fallback."""
        now = clock.farm_now()
        if not force_refresh and self.is_cache_valid() and self._cached_forecast is not None:
            result = self._cached_forecast.model_copy()
            result.cached = True
            return result

        try:
            forecast = await self._fetch_open_meteo()
            self._cached_forecast = forecast
            self._cache_time = now
            self._last_success_time = now
            self._last_error = None

            # Persist to database cache asynchronously if session provided
            if db is not None:
                await self._persist_db_cache(db, forecast)

            return forecast
        except Exception as exc:
            self._last_error = type(exc).__name__
            log.warning("Failed to fetch weather from Open-Meteo: %s", self._last_error)

            # 1. Fallback to in-memory cached forecast if exists (even if expired)
            if self._cached_forecast is not None:
                log.info("Serving stale in-memory weather forecast cache")
                stale = self._cached_forecast.model_copy()
                stale.cached = True
                return stale

            # 2. Fallback to database cache if session provided
            if db is not None:
                db_cached = await self._load_db_cache(db)
                if db_cached is not None:
                    log.info("Serving database weather forecast cache")
                    self._cached_forecast = db_cached
                    self._cache_time = as_utc(datetime.fromisoformat(db_cached.last_fetched_at))
                    return db_cached

            return None

    async def _fetch_open_meteo(self) -> WeatherForecast:
        """Fetch raw JSON from Open-Meteo API."""
        params = {
            "latitude": settings.weather_latitude,
            "longitude": settings.weather_longitude,
            "timezone": settings.weather_timezone,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,weather_code,cloud_cover",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,et0_fao_evapotranspiration,weather_code,cloud_cover",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration,weather_code",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        now_iso = clock.farm_now().isoformat()

        # Parse current
        cur_raw = data.get("current", {})
        current_timestamp = cur_raw.get("time")
        if not isinstance(current_timestamp, str):
            raise ValueError("Current weather timestamp is missing")
        datetime.fromisoformat(current_timestamp)
        current_values = _observations(cur_raw, _CURRENT_FIELDS)
        if current_values is None:
            raise ValueError("Current weather observations are incomplete")
        cur_wmo = _interpret_wmo(cur_raw.get("weather_code"))
        current = WeatherData(
            timestamp=current_timestamp,
            **current_values,
            condition=cur_wmo["condition"],
            description=cur_wmo["en"],
            description_ar=cur_wmo["ar"],
        )

        # Parse daily
        daily_list: list[WeatherDaySummary] = []
        daily_raw = data.get("daily", {})
        times = daily_raw.get("time", [])
        w_codes = daily_raw.get("weather_code", [])

        for i, date_str in enumerate(times):
            values = _observations(daily_raw, _DAILY_FIELDS, i)
            if values is None:
                continue
            try:
                date.fromisoformat(date_str)
            except (ValueError, TypeError):
                continue
            code = w_codes[i] if i < len(w_codes) else None
            wmo = _interpret_wmo(code)
            daily_list.append(
                WeatherDaySummary(
                    date=date_str,
                    **values,
                    condition=wmo["condition"],
                    description=wmo["en"],
                    description_ar=wmo["ar"],
                )
            )

        # Parse hourly (take first 48 hours)
        hourly_list: list[WeatherData] = []
        hourly_raw = data.get("hourly", {})
        h_times = hourly_raw.get("time", [])
        h_codes = hourly_raw.get("weather_code", [])

        limit = min(48, len(h_times))
        for j in range(limit):
            values = _observations(hourly_raw, _HOURLY_FIELDS, j)
            if values is None:
                continue
            try:
                datetime.fromisoformat(h_times[j])
            except (ValueError, TypeError):
                continue
            code = h_codes[j] if j < len(h_codes) else None
            wmo = _interpret_wmo(code)
            hourly_list.append(
                WeatherData(
                    timestamp=h_times[j],
                    **values,
                    condition=wmo["condition"],
                    description=wmo["en"],
                    description_ar=wmo["ar"],
                )
            )

        return WeatherForecast(
            current=current,
            hourly=hourly_list,
            daily=daily_list,
            last_fetched_at=now_iso,
            source="open-meteo",
            cached=False,
        )

    async def _persist_db_cache(self, db: AsyncSession, forecast: WeatherForecast) -> None:
        try:
            now = clock.farm_now()
            entry = WeatherCache(
                timestamp=now,
                temperature_c=forecast.current.temperature_c,
                humidity_pct=forecast.current.humidity_pct,
                wind_speed_kmh=forecast.current.wind_speed_kmh,
                precipitation_mm=forecast.current.precipitation_mm,
                precipitation_probability_pct=forecast.current.precipitation_probability_pct,
                cloud_cover_pct=forecast.current.cloud_cover_pct,
                condition=forecast.current.condition,
                description=forecast.current.description,
                description_ar=forecast.current.description_ar,
                source="open-meteo",
                is_forecast=True,
                fetched_at=now,
                raw_payload_json=json.dumps({**forecast.model_dump(), _VALIDATED_CACHE: True}),
                et0_mm=forecast.daily[0].et0_mm if forecast.daily else None,
            )
            async with db.begin_nested():
                db.add(entry)
        except Exception as exc:
            log.warning("Could not persist weather cache in DB: %s", type(exc).__name__)

    async def _load_db_cache(self, db: AsyncSession) -> WeatherForecast | None:
        try:
            stmt = select(WeatherCache).order_by(desc(WeatherCache.fetched_at)).limit(1)
            res = await db.execute(stmt)
            row = res.scalar_one_or_none()
            if row and row.raw_payload_json:
                data = json.loads(row.raw_payload_json)
                if not data.get(_VALIDATED_CACHE):
                    return None
                forecast = WeatherForecast(**data)
                forecast.cached = True
                return forecast
        except Exception as exc:
            log.warning("Error loading weather cache from DB: %s", type(exc).__name__)
        return None

    def health(self) -> dict[str, Any]:
        """Return health status for /health router."""
        now = clock.farm_now()
        age_sec = (now - self._cache_time).total_seconds() if self._cache_time is not None else None
        has_cache = self._cached_forecast is not None
        status = (
            "healthy"
            if has_cache and age_sec is not None and 0 <= age_sec < settings.weather_cache_ttl_sec
            else "degraded"
        )
        if not has_cache and self._last_error:
            status = "unavailable"

        return {
            "status": status,
            "provider": "open-meteo",
            "latitude": settings.weather_latitude,
            "longitude": settings.weather_longitude,
            "timezone": settings.weather_timezone,
            "cache_age_sec": age_sec,
            "last_error": self._last_error,
            "last_success": self._last_success_time.isoformat()
            if self._last_success_time
            else None,
        }


weather_service = WeatherService()
