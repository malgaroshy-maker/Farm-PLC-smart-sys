// Glass widget top-right of the map, above zoom controls.
// Props: forecast: WeatherData | null, hourly: WeatherData[], lang: Lang
// Wind direction: meteorological "from" convention (arrow points toward source)

import { useState } from 'react';
import type { WeatherData } from '../../lib/api';
import { translate, useI18nStore, type Lang, type MsgKey } from '../../lib/i18n';
import { usePrefs } from '../../lib/prefs';
import { conditionIcon, parseWindDirection } from './weatherUtils';

function formatHour(ts: string, lang: Lang): string {
  try {
    const d = new Date(ts.includes('Z') || /[+-]\d{2}/.test(ts) ? ts : `${ts}Z`);
    return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-LY' : 'en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Africa/Tripoli',
    }).format(d);
  } catch {
    return ts.slice(11, 16) || ts;
  }
}

export default function WeatherWidget({
  forecast,
  hourly = [],
  lang: propLang,
}: {
  forecast: WeatherData | null;
  hourly?: WeatherData[];
  lang?: Lang;
}) {
  const storeLang = useI18nStore((s) => s.lang);
  const lang = propLang ?? storeLang;
  const t = (k: MsgKey) => translate(lang, k);
  const reduceMotion = usePrefs((s) => s.reduceMotion);

  const [tooltipOpen, setTooltipOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState(false);

  // No-data state
  if (!forecast) {
    return (
      <div
        data-testid="weather-widget-no-data"
        className="panel px-3 py-1.5 text-xs text-[#849396] flex items-center gap-2 select-none shadow-lg"
      >
        <span aria-hidden="true">🌤️</span>
        <span>{t('weather.noData')}</span>
      </div>
    );
  }

  const windAngle = parseWindDirection(forecast.wind_direction, forecast.wind_direction_10m);
  const icon = conditionIcon(forecast.condition);
  const rainProb = forecast.precipitation_probability_pct ?? 0;
  const next6 = hourly.slice(0, 6);

  const windArrow = (
    <svg
      data-testid="wind-arrow"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transform: `rotate(${windAngle}deg)` }}
      transform={`rotate(${windAngle})`}
      className={reduceMotion ? '' : 'transition-transform duration-300'}
      aria-label={`Wind direction ${windAngle}°`}
    >
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );

  return (
    <div
      data-testid="weather-widget"
      className="relative select-none"
      onMouseEnter={() => setTooltipOpen(true)}
      onMouseLeave={() => setTooltipOpen(false)}
      onClick={() => setTooltipOpen((v) => !v)}
    >
      {/* Mobile collapsed chip (< 640px) */}
      <div className="sm:hidden">
        {!mobileExpanded ? (
          <button
            type="button"
            onClick={() => setMobileExpanded(true)}
            data-testid="weather-mobile-chip"
            className="panel px-2.5 py-1.5 flex items-center gap-1.5 text-xs text-[#e5e2e1] hover:bg-white/10 shadow-lg"
            aria-label="Expand weather details"
          >
            <span>{icon}</span>
            <bdi className="font-mono font-medium">{forecast.temperature_c}°C</bdi>
            {rainProb > 0 && (
              <span className="text-cyan-400 text-[10px]">💧{rainProb}%</span>
            )}
          </button>
        ) : (
          <div
            className="panel p-2 text-xs flex flex-col gap-1.5 shadow-xl text-[#e5e2e1] cursor-pointer"
            onClick={() => setMobileExpanded(false)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Escape' || e.key === 'Enter') setMobileExpanded(false);
            }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5">
                <span className="text-base">{icon}</span>
                <bdi className="font-mono text-sm font-semibold">{forecast.temperature_c}°C</bdi>
              </div>
              <div className="flex items-center gap-1 text-[#bac9cc]">
                {windArrow}
                <bdi className="font-mono text-[11px]">{forecast.wind_speed_kmh} km/h</bdi>
              </div>
              {rainProb > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 font-mono text-[11px]">
                  💧 {rainProb}%
                </span>
              )}
            </div>
            {next6.length > 0 && (
              <div className="pt-1.5 border-t border-white/10 grid grid-cols-6 gap-1 text-center text-[10px]">
                {next6.map((item, idx) => (
                  <div key={item.timestamp || idx} className="flex flex-col items-center">
                    <span className="text-[#849396]">{formatHour(item.timestamp, lang)}</span>
                    <span>{conditionIcon(item.condition)}</span>
                    <bdi className="font-mono font-medium">{item.temperature_c}°</bdi>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Desktop full panel (>= 640px) */}
      <div
        className="hidden sm:flex panel px-3 py-1.5 items-center gap-3 text-xs text-[#e5e2e1] shadow-xl cursor-pointer"
        onClick={() => setTooltipOpen((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') setTooltipOpen((v) => !v);
        }}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-base">{icon}</span>
          <bdi className="font-mono text-sm font-semibold">{forecast.temperature_c}°C</bdi>
        </div>

        <div className="flex items-center gap-1 text-[#bac9cc]" title={t('weather.wind')}>
          {windArrow}
          <bdi className="font-mono text-[11px]">{forecast.wind_speed_kmh} km/h</bdi>
        </div>

        {rainProb > 0 && (
          <span
            className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 font-mono text-[11px]"
            title={t('weather.rain')}
          >
            💧 {rainProb}%
          </span>
        )}
      </div>

      {/* Hourly tooltip on hover or tap */}
      {tooltipOpen && next6.length > 0 && (
        <div
          data-testid="weather-hourly-tooltip"
          className="absolute z-40 top-full mt-2 end-0 panel p-2.5 text-xs shadow-2xl min-w-56"
          role="tooltip"
        >
          <div className="text-[11px] font-semibold text-[#849396] mb-2">{t('weather.next6h')}</div>
          <div className="grid grid-cols-6 gap-2 text-center">
            {next6.map((item, idx) => {
              const itemRain = item.precipitation_probability_pct ?? 0;
              return (
                <div key={item.timestamp || idx} className="flex flex-col items-center gap-0.5">
                  <span className="text-[10px] text-[#849396] font-mono">{formatHour(item.timestamp, lang)}</span>
                  <span className="text-sm">{conditionIcon(item.condition)}</span>
                  <bdi className="font-mono text-xs font-semibold">{item.temperature_c}°</bdi>
                  {itemRain > 0 ? (
                    <span className="text-[9px] text-cyan-400 font-mono">{itemRain}%</span>
                  ) : (
                    <span className="text-[9px] text-[#849396]">—</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
