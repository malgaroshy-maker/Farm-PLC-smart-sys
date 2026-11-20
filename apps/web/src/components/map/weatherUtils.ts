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
