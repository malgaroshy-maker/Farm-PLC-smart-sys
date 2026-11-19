import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { fetchZoneBaseline, type ZoneBaseline } from '../../lib/api';
import { fmtNum, useT, type MsgKey } from '../../lib/i18n';
import { FlowIcon, GaugeIcon } from '../icons/FarmIcons';

interface BaselineSectionProps {
  zoneId: string;
  currentFlow?: number | null;
  currentPressure?: number | null;
}

export default function BaselineSection({ zoneId, currentFlow, currentPressure }: BaselineSectionProps) {
  const { t } = useT();
  const [baseline, setBaseline] = useState<ZoneBaseline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetchZoneBaseline(zoneId)
      .then((data) => {
        if (!active) return;
        setBaseline(data);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setBaseline(null);
        setError(err instanceof Error ? err.message : t('baseline.error'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [zoneId, t]);

  if (loading && !baseline && !error) {
    return (
      <section className="panel p-4 space-y-2 animate-pulse">
        <div className="h-4 bg-white/10 rounded w-1/3" />
        <div className="grid grid-cols-2 gap-2">
          <div className="h-14 bg-white/5 rounded-xl" />
          <div className="h-14 bg-white/5 rounded-xl" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel p-3.5 border-[#ff5449]/30 bg-[#ff5449]/10 text-xs text-[#ffb4ab] flex items-center gap-2">
        <AlertTriangle size={16} className="shrink-0 text-[#ff5449]" />
        <span>{error}</span>
      </section>
    );
  }

  if (!baseline) return null;

  // If baseline is not calibrated yet (fewer than 5 runs)
  const isCalibrated = Boolean(baseline.calibrated || baseline.is_calibrated);
  const completedRuns = baseline.runs_completed ?? baseline.baseline_cycles_count ?? 0;
  const requiredRuns = baseline.runs_required ?? 5;

  if (!isCalibrated) {
    return (
      <section className="panel p-4 space-y-2 border-white/10 bg-black/20">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-[#00e5ff]" />
            <span className="text-xs font-bold text-[#bac9cc]">{t('baseline.title')}</span>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/5 text-[#849396] border border-white/5">
            {completedRuns}/{requiredRuns}
          </span>
        </div>
        <div className="p-3 rounded-xl bg-white/5 border border-white/5 flex items-center gap-2.5 text-xs text-[#bac9cc]">
          <Clock size={16} className="text-[#ffeb3b] shrink-0" />
          <span>
            {t('baseline.notCalibrated').replace('{n}', String(completedRuns))}
          </span>
        </div>
      </section>
    );
  }

  // Determine live status if current values are available
  let status = baseline.status ?? 'normal';
  if (
    currentFlow != null &&
    currentPressure != null &&
    currentFlow > 0.5 &&
    baseline.flow_max_normal_m3h != null &&
    baseline.pressure_min_normal_bar != null &&
    baseline.flow_min_normal_m3h != null &&
    baseline.pressure_max_normal_bar != null
  ) {
    if (currentFlow > baseline.flow_max_normal_m3h && currentPressure < baseline.pressure_min_normal_bar) {
      status = 'high_flow_low_pressure';
    } else if (currentFlow < baseline.flow_min_normal_m3h && currentPressure > baseline.pressure_max_normal_bar) {
      status = 'low_flow_high_pressure';
    } else {
      status = 'normal';
    }
  }

  const isAlarm = status === 'high_flow_low_pressure' || status === 'low_flow_high_pressure';
  const statusColor = isAlarm ? '#ff9f43' : status === 'normal' ? '#7ee787' : '#849396';

  return (
    <section className="panel p-4 space-y-3">
      {/* Title & Status */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-[#00e5ff]" />
          <span className="text-xs font-bold text-[#bac9cc]">{t('baseline.title')}</span>
        </div>
        <span
          className="text-[11px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 border"
          style={{
            color: statusColor,
            borderColor: `${statusColor}44`,
            backgroundColor: `${statusColor}15`,
          }}
        >
          {isAlarm ? <AlertTriangle size={12} /> : <CheckCircle size={12} />}
          <span>{t(`baseline.status.${status}` as MsgKey)}</span>
        </span>
      </div>

      {/* Two columns: Flow band & Pressure band */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {/* Flow Band */}
        <div className="p-2.5 rounded-xl bg-black/25 border border-white/5 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-[#849396]">
            <FlowIcon size={14} accent="#00e5ff" />
            <span>{t('baseline.flowBand')}</span>
          </div>
          <div className="font-mono text-sm font-bold text-[#e5e2e1]" dir="ltr">
            {fmtNum(baseline.flow_min_normal_m3h ?? 0, 1)} – {fmtNum(baseline.flow_max_normal_m3h ?? 0, 1)}{' '}
            <span className="text-[10px] text-[#849396] font-normal">m³/h</span>
          </div>
          <div className="text-[10px] text-[#849396] font-mono" dir="ltr">
            Median: {fmtNum(baseline.flow_median_m3h ?? 0, 1)} m³/h
          </div>
        </div>

        {/* Pressure Band */}
        <div className="p-2.5 rounded-xl bg-black/25 border border-white/5 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-[#849396]">
            <GaugeIcon size={14} accent="#00e5ff" />
            <span>{t('baseline.pressureBand')}</span>
          </div>
          <div className="font-mono text-sm font-bold text-[#e5e2e1]" dir="ltr">
            {fmtNum(baseline.pressure_min_normal_bar ?? 0, 2)} – {fmtNum(baseline.pressure_max_normal_bar ?? 0, 2)}{' '}
            <span className="text-[10px] text-[#849396] font-normal">bar</span>
          </div>
          <div className="text-[10px] text-[#849396] font-mono" dir="ltr">
            Median: {fmtNum(baseline.pressure_median_bar ?? 0, 2)} bar
          </div>
        </div>
      </div>

      {/* Baseline Calibration Info */}
      <div className="text-[10px] text-[#849396] flex items-center justify-between border-t border-white/5 pt-2">
        <span>{t('baseline.cyclesCount')}: {completedRuns}</span>
        <span className="font-mono">Median + MAD (Robust Z-Score)</span>
      </div>
    </section>
  );
}
