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
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.models.ai import WeatherCache

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

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


class WeatherData(BaseModel):
    timestamp: str
    temperature_c: float
    humidity_pct: float
    wind_speed_kmh: float
    wind_direction: str = "N"
    precipitation_mm: float = 0.0
    precipitation_probability_pct: float = 0.0
    cloud_cover_pct: float = 0.0
    uv_index: float = 0.0
    et0_mm: float = 0.0
    condition: str = "clear"
    description: str = "Clear"
    description_ar: str = "صافٍ"


class WeatherDaySummary(BaseModel):
    date: str  # YYYY-MM-DD
    temp_min_c: float
    temp_max_c: float
    humidity_avg_pct: float = 50.0
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

    def is_cache_valid(self) -> bool:
        if self._cached_forecast is None or self._cache_time is None:
            return False
        age_sec = (clock.farm_now() - self._cache_time).total_seconds()
        return age_sec < settings.weather_cache_ttl_sec

    async def get_forecast(
        self, db: AsyncSession | None = None, force_refresh: bool = False
    ) -> WeatherForecast:
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
            self._last_error = str(exc)
            log.warning("Failed to fetch weather from Open-Meteo: %s", exc)

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
                    self._cache_time = now
                    return db_cached

            # 3. Last-resort synthetic fallback for Algaroshy Farm
            log.warning("Serving default synthetic weather fallback")
            return self._build_default_fallback(now)

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
        cur_wmo = _interpret_wmo(cur_raw.get("weather_code"))
        current = WeatherData(
            timestamp=cur_raw.get("time", now_iso),
            temperature_c=float(cur_raw.get("temperature_2m", 25.0)),
            humidity_pct=float(cur_raw.get("relative_humidity_2m", 50.0)),
            wind_speed_kmh=float(cur_raw.get("wind_speed_10m", 10.0)),
            wind_direction=str(cur_raw.get("wind_direction_10m", "0")),
            precipitation_mm=float(cur_raw.get("precipitation", 0.0)),
            precipitation_probability_pct=0.0,
            cloud_cover_pct=float(cur_raw.get("cloud_cover", 0.0)),
            uv_index=0.0,
            et0_mm=0.0,
            condition=cur_wmo["condition"],
            description=cur_wmo["en"],
            description_ar=cur_wmo["ar"],
        )

        # Parse daily
        daily_list: list[WeatherDaySummary] = []
        daily_raw = data.get("daily", {})
        times = daily_raw.get("time", [])
        t_max = daily_raw.get("temperature_2m_max", [])
        t_min = daily_raw.get("temperature_2m_min", [])
        p_sum = daily_raw.get("precipitation_sum", [])
        p_prob = daily_raw.get("precipitation_probability_max", [])
        et0_list = daily_raw.get("et0_fao_evapotranspiration", [])
        w_codes = daily_raw.get("weather_code", [])

        for i, date_str in enumerate(times):
            code = w_codes[i] if i < len(w_codes) else None
            wmo = _interpret_wmo(code)
            daily_list.append(
                WeatherDaySummary(
                    date=date_str,
                    temp_min_c=float(t_min[i]) if i < len(t_min) and t_min[i] is not None else 18.0,
                    temp_max_c=float(t_max[i]) if i < len(t_max) and t_max[i] is not None else 32.0,
                    precipitation_total_mm=float(p_sum[i])
                    if i < len(p_sum) and p_sum[i] is not None
                    else 0.0,
                    precipitation_probability_pct=float(p_prob[i])
                    if i < len(p_prob) and p_prob[i] is not None
                    else 0.0,
                    et0_mm=float(et0_list[i])
                    if i < len(et0_list) and et0_list[i] is not None
                    else 4.5,
                    condition=wmo["condition"],
                    description=wmo["en"],
                    description_ar=wmo["ar"],
                )
            )

        # Parse hourly (take first 48 hours)
        hourly_list: list[WeatherData] = []
        hourly_raw = data.get("hourly", {})
        h_times = hourly_raw.get("time", [])
        h_temp = hourly_raw.get("temperature_2m", [])
        h_hum = hourly_raw.get("relative_humidity_2m", [])
        h_precip = hourly_raw.get("precipitation", [])
        h_prob = hourly_raw.get("precipitation_probability", [])
        h_wind = hourly_raw.get("wind_speed_10m", [])
        h_cloud = hourly_raw.get("cloud_cover", [])
        h_et0 = hourly_raw.get("et0_fao_evapotranspiration", [])
        h_codes = hourly_raw.get("weather_code", [])

        limit = min(48, len(h_times))
        for j in range(limit):
            code = h_codes[j] if j < len(h_codes) else None
            wmo = _interpret_wmo(code)
            hourly_list.append(
                WeatherData(
                    timestamp=h_times[j],
                    temperature_c=float(h_temp[j])
                    if j < len(h_temp) and h_temp[j] is not None
                    else 25.0,
                    humidity_pct=float(h_hum[j])
                    if j < len(h_hum) and h_hum[j] is not None
                    else 50.0,
                    wind_speed_kmh=float(h_wind[j])
                    if j < len(h_wind) and h_wind[j] is not None
                    else 10.0,
                    precipitation_mm=float(h_precip[j])
                    if j < len(h_precip) and h_precip[j] is not None
                    else 0.0,
                    precipitation_probability_pct=float(h_prob[j])
                    if j < len(h_prob) and h_prob[j] is not None
                    else 0.0,
                    cloud_cover_pct=float(h_cloud[j])
                    if j < len(h_cloud) and h_cloud[j] is not None
                    else 0.0,
                    et0_mm=float(h_et0[j]) if j < len(h_et0) and h_et0[j] is not None else 0.2,
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
                raw_payload_json=forecast.model_dump_json(),
                et0_mm=forecast.daily[0].et0_mm if forecast.daily else 0.0,
            )
            db.add(entry)
            await db.commit()
        except Exception as exc:
            log.warning("Could not persist weather cache in DB: %s", exc)

    async def _load_db_cache(self, db: AsyncSession) -> WeatherForecast | None:
        try:
            stmt = select(WeatherCache).order_by(desc(WeatherCache.fetched_at)).limit(1)
            res = await db.execute(stmt)
            row = res.scalar_one_or_none()
            if row and row.raw_payload_json:
                data = json.loads(row.raw_payload_json)
                forecast = WeatherForecast(**data)
                forecast.cached = True
                return forecast
        except Exception as exc:
            log.warning("Error loading weather cache from DB: %s", exc)
        return None

    def _build_default_fallback(self, now: datetime) -> WeatherForecast:
        now_iso = now.isoformat()
        current = WeatherData(
            timestamp=now_iso,
            temperature_c=28.0,
            humidity_pct=45.0,
            wind_speed_kmh=12.0,
            wind_direction="180",
            precipitation_mm=0.0,
            precipitation_probability_pct=0.0,
            cloud_cover_pct=0.0,
            et0_mm=5.0,
            condition="clear",
            description="Clear sky (offline fallback)",
            description_ar="سماء صافية (احتياطي دون اتصال)",
        )
        today_date = now.strftime("%Y-%m-%d")
        daily = [
            WeatherDaySummary(
                date=today_date,
                temp_min_c=19.0,
                temp_max_c=31.0,
                precipitation_total_mm=0.0,
                precipitation_probability_pct=0.0,
                et0_mm=5.2,
                condition="clear",
                description="Clear sky (offline fallback)",
                description_ar="سماء صافية (احتياطي دون اتصال)",
            )
        ]
        return WeatherForecast(
            current=current,
            hourly=[current],
            daily=daily,
            last_fetched_at=now_iso,
            source="offline_fallback",
            cached=True,
        )

    def health(self) -> dict[str, Any]:
        """Return health status for /health router."""
        now = clock.farm_now()
        age_sec = (now - self._cache_time).total_seconds() if self._cache_time is not None else None
        has_cache = self._cached_forecast is not None
        status = (
            "healthy"
            if has_cache and (age_sec is None or age_sec < settings.weather_cache_ttl_sec * 2)
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
