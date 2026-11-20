import type { WeatherData } from '../../lib/api';

/**
 * Meteorological convention for wind direction:
 * Reports the direction FROM which the wind originates.
 * For example, if wind_direction_10m = 180° (wind FROM south → blowing north),
 * the arrow points south (180°, toward the source).
 */
export function parseWindDirection(dir: string | number | undefined, dir10m?: number): number {
  if (typeof dir10m === 'number') return dir10m;
  if (typeof dir === 'number') return dir;
  if (!dir) return 0;
  const num = parseFloat(dir);
  if (!Number.isNaN(num)) return num;
  const CARDINALS: Record<string, number> = {
    N: 0,
    NNE: 22.5,
    NE: 45,
    ENE: 67.5,
    E: 90,
    ESE: 112.5,
    SE: 135,
    SSE: 157.5,
    S: 180,
    SSW: 202.5,
    SW: 225,
    WSW: 247.5,
    W: 270,
    WNW: 292.5,
    NW: 315,
    NNW: 337.5,
  };
  return CARDINALS[dir.toUpperCase()] ?? 0;
}

export function conditionIcon(condition?: string): string {
  if (!condition) return '🌤️';
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('drizzle') || c.includes('shower')) return '🌧️';
  if (c.includes('thunder') || c.includes('storm')) return '⛈️';
  if (c.includes('snow')) return '❄️';
  if (c.includes('cloud') || c.includes('overcast')) return '☁️';
  if (c.includes('fog') || c.includes('mist')) return '🌫️';
  return '🌤️';
}

export function isRaining(forecast: WeatherData | null | undefined): boolean {
  if (!forecast) return false;
  const condition = (forecast.condition || '').toLowerCase();
  const hasRainWord =
    condition.includes('rain') || condition.includes('drizzle') || condition.includes('shower');
  const prob = forecast.precipitation_probability_pct ?? 0;
  return hasRainWord || prob >= 60;
}

export interface ActiveWeatherSelection {
  current: WeatherData | null;
  next6: WeatherData[];
  inRange: boolean;
}

/**
 * Select the forecast and next 6 hourly items matching current farm time (Africa/Tripoli).
 * If farm time is outside the forecast range, returns { current: null, next6: [], inRange: false }.
 */
export function selectForecastForFarmTime(
  forecast: { current?: WeatherData; hourly?: WeatherData[] } | null,
  farmNowIso: string
): ActiveWeatherSelection {
  if (!forecast || !forecast.hourly || forecast.hourly.length === 0) {
    return { current: null, next6: [], inRange: false };
  }

  const farmTime = new Date(
    farmNowIso.includes('Z') || /[+-]\d{2}/.test(farmNowIso) ? farmNowIso : `${farmNowIso}Z`
  );
  const farmTimeMs = farmTime.getTime();
  if (Number.isNaN(farmTimeMs)) {
    return { current: null, next6: [], inRange: false };
  }

  const parsedHourly = forecast.hourly.map((h) => {
    const tsStr =
      h.timestamp.includes('Z') || /[+-]\d{2}/.test(h.timestamp)
        ? h.timestamp
        : `${h.timestamp}+02:00`;
    const tMs = new Date(tsStr).getTime();
    return { item: h, tMs };
  });

  const firstMs = parsedHourly[0].tMs;
  const lastMs = parsedHourly[parsedHourly.length - 1].tMs;

  // If farm time is before forecast starts or after it ends (with 30m grace), it is out of range
  if (farmTimeMs < firstMs - 30 * 60 * 1000 || farmTimeMs > lastMs + 60 * 60 * 1000) {
    return { current: null, next6: [], inRange: false };
  }

  // Find closest hourly entry
  let bestIdx = 0;
  let minDiff = Math.abs(parsedHourly[0].tMs - farmTimeMs);
  for (let i = 1; i < parsedHourly.length; i++) {
    const diff = Math.abs(parsedHourly[i].tMs - farmTimeMs);
    if (diff < minDiff) {
      minDiff = diff;
      bestIdx = i;
    }
  }

  // If closest entry is more than 90m away, consider out of range
  if (minDiff > 90 * 60 * 1000) {
    return { current: null, next6: [], inRange: false };
  }

  const current = parsedHourly[bestIdx].item;
  const next6 = parsedHourly.slice(bestIdx + 1, bestIdx + 7).map((p) => p.item);

  return { current, next6, inRange: true };
}
