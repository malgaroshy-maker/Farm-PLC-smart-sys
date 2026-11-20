import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Calendar, CloudRain, AlertCircle } from 'lucide-react';
import { fetchDailyBriefing, type DailyBriefing } from '../../lib/api';
import { fmtNum, pickName, useT } from '../../lib/i18n';
import { AiSparklesIcon, DropIcon, WeatherIcon } from '../icons/FarmIcons';
import ModelBadge from './ModelBadge';

interface DailyBriefingCardProps {
  initialCollapsed?: boolean;
}

export default function DailyBriefingCard({ initialCollapsed = false }: DailyBriefingCardProps) {
  const { t, lang } = useT();
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchDailyBriefing()
      .then((res) => {
        if (!active) return;
        setBriefing(res);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setBriefing(null);
        setError(err instanceof Error ? err.message : 'Failed to load daily briefing');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (loading && !briefing && !error) {
    return (
      <div className="panel p-4 animate-pulse space-y-3">
        <div className="flex justify-between items-center">
          <div className="h-5 bg-white/10 rounded w-1/3" />
          <div className="h-5 bg-white/10 rounded w-16" />
        </div>
        <div className="h-12 bg-white/5 rounded-xl" />
      </div>
    );
  }

  if (error && !briefing) {
    return (
      <div className="panel p-3.5 border-[#ff5449]/20 bg-[#ff5449]/5 text-xs text-[#ffb4ab] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AlertCircle size={16} className="text-[#ff5449] shrink-0" />
          <span>{t('briefing.title')}: {error}</span>
        </div>
      </div>
    );
  }

  if (!briefing) return null;

  const recapText = pickName(lang, briefing.morning_recap, briefing.morning_recap_ar);
  const forecast = briefing.weather_forecast;
  const activeModel = briefing.model_used || briefing.model;

  return (
    <article
      aria-label={t('briefing.title')}
      className="panel p-4 sm:p-5 relative overflow-hidden border-[#00e5ff]/20 bg-gradient-to-br from-[#161d20]/80 via-[#141416]/90 to-[#101416]/90 shadow-xl transition-all"
    >
      {/* Decorative accent glow */}
      <div className="absolute top-0 end-0 w-64 h-32 bg-[#00e5ff]/5 blur-3xl pointer-events-none rounded-full" />

      {/* Header bar */}
      <div className="flex items-center justify-between gap-3 border-b border-white/5 pb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="p-2 rounded-xl bg-[#00e5ff]/15 text-[#00e5ff] shrink-0">
            <AiSparklesIcon size={20} />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-bold text-[#e5e2e1] leading-tight truncate">
              {t('briefing.title')}
            </h2>
            <p className="text-xs text-[#849396] truncate">
              {briefing.date} · {t('briefing.subtitle')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          {briefing.is_fallback ? (
            <span className="hidden sm:inline-block text-[11px] px-2 py-0.5 rounded-full bg-white/5 text-[#849396] border border-white/5 font-medium">
              {t('ai.ruleBasedLabel')}
            </span>
          ) : (
            <div className="hidden sm:flex items-center gap-1.5">
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/20 font-medium">
                {briefing.provider || 'APInex'}
              </span>
              {activeModel && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-[#bac9cc] border border-white/10">
                  {activeModel}
                </span>
              )}
            </div>
          )}

          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-expanded={!collapsed}
            aria-label={collapsed ? t('briefing.expand') : t('briefing.collapse')}
            className="p-1.5 rounded-lg text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1] transition-colors"
          >
            {collapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
        </div>
      </div>

      {/* Recap text (always visible or expandable) */}
      <div className="pt-3 space-y-2">
        <p className="text-xs sm:text-sm text-[#bac9cc] leading-relaxed">
          {recapText}
        </p>
        <div className="pt-1">
          <ModelBadge modelUsed={briefing.model_used || briefing.model} provider={briefing.provider} />
        </div>
      </div>

      {/* Collapsible Key Indicators: Water used, Today's programs, Weather */}
      {!collapsed && (
        <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* 1. Water Used Yesterday */}
          <div className="p-3 rounded-xl bg-black/25 border border-white/5 flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-[#00e5ff]/10 text-[#00e5ff]">
              <DropIcon size={20} />
            </span>
            <div className="min-w-0">
              <div className="text-[11px] text-[#849396]">{t('briefing.waterYesterday')}</div>
              <div className="text-lg font-bold font-mono text-[#e5e2e1]">
                {fmtNum(briefing.water_used_yesterday_m3, 1)}{' '}
                <span className="text-xs font-normal text-[#849396]">m³</span>
              </div>
            </div>
          </div>

          {/* 2. Today's Schedules */}
          <div className="p-3 rounded-xl bg-black/25 border border-white/5 flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-[#ffeb3b]/10 text-[#ffeb3b]">
              <Calendar size={20} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] text-[#849396]">{t('briefing.todayPlan')}</div>
              {briefing.schedules_today && briefing.schedules_today.length > 0 ? (
                <div className="text-xs font-bold text-[#e5e2e1] truncate">
                  <span className="font-mono text-[#00e5ff]">{briefing.schedules_today[0].start_time}</span>{' '}
                  {briefing.schedules_today[0].program_name_ar || briefing.schedules_today[0].program_name}
                  {briefing.schedules_today.length > 1 && (
                    <span className="text-[10px] text-[#849396] ms-1">
                      (+{briefing.schedules_today.length - 1})
                    </span>
                  )}
                </div>
              ) : (
                <div className="text-xs text-[#849396]">{t('briefing.noPrograms')}</div>
              )}
            </div>
          </div>

          {/* 3. Weather Forecast at Farm Site */}
          <div className="p-3 rounded-xl bg-black/25 border border-white/5 flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-[#00e5ff]/10 text-[#00e5ff]">
              <WeatherIcon condition={forecast.condition} size={20} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] text-[#849396]">{t('briefing.forecast')}</div>
              <div className="flex items-center gap-2 text-xs font-bold text-[#e5e2e1]">
                <span className="font-mono">{fmtNum(forecast.temp_max_c)}° / {fmtNum(forecast.temp_min_c)}°C</span>
                {forecast.rain_prob_pct > 0 && (
                  <span className="flex items-center gap-0.5 text-[11px] text-[#00e5ff] font-mono">
                    <CloudRain size={12} />
                    {forecast.rain_prob_pct}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
