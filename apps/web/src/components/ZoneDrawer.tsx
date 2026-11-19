import { useEffect, useState } from 'react';
import { Play, Square, X } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { IrrigationCycle, TelemetrySeries, Zone, Alarm } from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';

import type { ZoneLiveState } from '../hooks/useFarmConnector';
import type { CommandOutcome } from '../store/farm';
import { useFarmStore } from '../store/farm';
import { useAuth } from '../lib/auth';
import { apiFetch } from '../lib/api';
import { SEVERITY } from '../lib/alarms';
import { fmtNum, pickName, useT, type MsgKey } from '../lib/i18n';
import { DropIcon, FlowIcon, GaugeIcon, ValveIcon, AiSparklesIcon } from './icons/FarmIcons';
import { CROP_ICON } from './icons/cropIcon';
import MaintenanceDone from './MaintenanceDone';
import { parseUtcDate, useClockStore } from '../lib/clock';
import BaselineSection from './ai/BaselineSection';
import ExplainAlarmDrawer from './ai/ExplainAlarmDrawer';

interface ZoneDrawerProps {
  zoneId: string | null;
  zoneState?: ZoneLiveState;
  onClose: () => void;
  onCommand?: (action: 'start' | 'stop', targetId: string, durationMin?: number) => Promise<CommandOutcome>;
}

type Feedback = { kind: 'ok' | 'error'; text: string } | null;
type ChartRow = { time: string; moisture?: number; flow?: number };

const SEED: Record<string, Zone> = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));
const DETAIL_ART: Record<string, string> = {
  pomegranate: '/art/detail_pomegranate.webp',
  olives: '/art/detail_olive.webp',
  grapes: '/art/detail_grape.webp',
  mixed_fruit: '/art/detail_stonefruit.webp',
};
const RANGES = [
  { label: '1H', minutes: 60 },
  { label: '6H', minutes: 360 },
  { label: '24H', minutes: 1440 },
];
const PRESETS = [15, 30, 45, 60];
const CYAN = '#00e5ff';
const ACTIVE_STATES = ['starting_pump', 'opening_valve', 'validating_flow', 'running', 'stopping'];

function hms(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function useZoneHistory(zoneId: string, minutes: number): ChartRow[] {
  const [rows, setRows] = useState<ChartRow[]>([]);
  const speed = useClockStore((s) => s.speed);
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const q = `zone_id=${encodeURIComponent(zoneId)}&minutes=${minutes}&points=60`;
        const [m, f] = await Promise.all([
          apiFetch<TelemetrySeries>(`/api/v1/telemetry/series?metric_key=zone.moisture_pct&${q}`),
          apiFetch<TelemetrySeries>(`/api/v1/telemetry/series?metric_key=zone.flow_m3h&${q}`),
        ]);
        const byTs = new Map<string, ChartRow>();
        const label = (ts: string) =>
          parseUtcDate(ts).toLocaleTimeString('en-GB', { timeZone: 'Africa/Tripoli', hour: '2-digit', minute: '2-digit' });
        m.points.forEach((p) => byTs.set(p.ts, { time: label(p.ts), moisture: p.value }));
        f.points.forEach((p) => byTs.set(p.ts, { ...(byTs.get(p.ts) ?? { time: label(p.ts) }), flow: p.value }));
        if (live) setRows([...byTs.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, r]) => r));
      } catch {
        if (live) setRows([]);
      }
    };
    void load();
    const interval = speed >= 60 ? 3000 : speed >= 10 ? 6000 : 15000;
    const id = setInterval(load, interval);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [zoneId, minutes, speed]);
  return rows;
}

export default function ZoneDrawer(props: ZoneDrawerProps) {
  if (!props.zoneId) return null;
  // Keyed by zone so feedback and the duration choice reset per zone.
  return <ZoneDrawerBody key={props.zoneId} {...props} zoneId={props.zoneId} />;
}

function ZoneDrawerBody({ zoneId, zoneState, onClose, onCommand }: ZoneDrawerProps & { zoneId: string }) {
  const { can } = useAuth();
  const { t, lang } = useT();
  const canControl = can('owner_admin', 'operator');
  const [config, setConfig] = useState<Zone | undefined>(SEED[zoneId]);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [explainingAlarm, setExplainingAlarm] = useState<Alarm | null>(null);
  const [range, setRange] = useState(RANGES[0]);
  const history = useZoneHistory(zoneId, range.minutes);
  const [recentCycles, setRecentCycles] = useState<IrrigationCycle[]>([]);

  useEffect(() => {
    let active = true;
    apiFetch<IrrigationCycle[]>(`/api/v1/cycles/recent/${zoneId}?limit=5`)
      .then((data) => {
        if (active) setRecentCycles(data);
      })
      .catch(() => {
        if (active) setRecentCycles([]);
      });
    return () => {
      active = false;
    };
  }, [zoneId, zoneState?.state]);
  const valve = useFarmStore((s) => s.state?.valves.find((v) => v.valve_id === `valve_${zoneId.slice(5)}` || v.zone_id === zoneId));
  const allAlarms = useFarmStore((s) => s.state?.active_alarms);
  const zoneAlarms = (allAlarms ?? []).filter((a) => a.zone_id === zoneId || a.device_id === `valve_${zoneId.slice(5)}`);

  useEffect(() => {
    apiFetch<Zone>(`/api/v1/zones/${zoneId}`)
      .then(setConfig)
      .catch(() => undefined);
  }, [zoneId]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const maxMin = config?.max_runtime_min ?? 120;
  const usual = config?.default_duration_min ?? 45;
  const duration = Math.min(maxMin, minutes ?? usual);
  const pick = (m: number) => {
    setMinutes(m);
    setConfirming(false);
  };

  const run = async (action: 'start' | 'stop') => {
    if (!onCommand) return;
    setBusy(true);
    setFeedback(null);
    const res = await onCommand(action, zoneId, action === 'start' ? duration : undefined);
    setBusy(false);
    setConfirming(false);
    setFeedback(
      res.ok
        ? { kind: 'ok', text: t(action === 'start' ? 'drawer.startOk' : 'drawer.stopOk') }
        : { kind: 'error', text: `${t('drawer.blocked')}: ${res.message}` },
    );
  };

  const state = zoneState?.state ?? 'unknown';
  const active = ACTIVE_STATES.includes(state);
  const isFault = state === 'faulted' || zoneState?.health === 'critical';
  const color = isFault ? SEVERITY.S3.color : state === 'running' ? CYAN : active ? '#ffeb3b' : '#849396';
  const target = zoneState?.target_runtime_sec ?? 0;
  const runtime = zoneState?.runtime_sec ?? 0;
  const progress = target > 0 ? Math.min(100, (runtime / target) * 100) : 0;
  const crop = config?.crop_type ?? 'pomegranate';
  const CropIcon = CROP_ICON[crop as keyof typeof CROP_ICON] ?? CROP_ICON.pomegranate;

  return (
    <>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-40" onClick={onClose} />
      <div className="fixed top-0 end-0 h-full w-[460px] max-w-full z-50 flex flex-col text-[#e5e2e1] bg-[#121214]/95 backdrop-blur-xl border-s border-white/10 shadow-2xl">
        <div className="p-5 flex items-start gap-3 border-b border-white/10">
          <span className="p-2 rounded-xl bg-white/5" style={{ color }}>
            <CropIcon size={26} />
          </span>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-bold truncate">{pickName(lang, config?.name, config?.name_ar) || zoneId}</h2>
            <div className="text-xs text-[#849396]">
              {t(`crop.${crop}` as MsgKey)} · <bdi className="font-mono">{fmtNum(config?.area_ha, 2)} ha</bdi>
            </div>
          </div>
          <button onClick={onClose} aria-label={t('drawer.close')} className="p-2 rounded-lg text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1]">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* 1 — status */}
          <section className="panel p-4 space-y-4" style={{ borderColor: `${color}55` }}>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${active ? 'animate-pulse' : ''}`} style={{ background: color }} />
              <span className="font-bold" style={{ color }}>
                {t(`state.${state}` as MsgKey)}
              </span>
              <span className="ms-auto text-xs text-[#849396]">
                {t('drawer.source')}: {zoneState?.source_mode ? t(`source.${zoneState.source_mode}` as MsgKey) : '—'}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Big icon={<DropIcon size={18} />} label={t('drawer.moisture')} value={fmtNum(zoneState?.moisture_pct, 1)} unit="%" />
              <Big icon={<FlowIcon size={18} />} label={t('drawer.flow')} value={fmtNum(zoneState?.flow_m3h, 1)} unit="m³/h" />
              <Big icon={<GaugeIcon size={18} />} label={t('drawer.pressure')} value={fmtNum(zoneState?.pressure_bar, 2)} unit="bar" />
            </div>
            {target > 0 && active && (
              <div>
                <div className="flex justify-between text-xs text-[#849396] mb-1.5">
                  <span>
                    {t('drawer.cycle')} <bdi className="font-mono text-[#e5e2e1]">{hms(runtime)}</bdi>
                  </span>
                  <span>
                    {t('drawer.remaining')} <bdi className="font-mono text-[#e5e2e1]">{hms(target - runtime)}</bdi>
                  </span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${progress}%`, background: `linear-gradient(90deg, ${CYAN}88, ${CYAN})` }} />
                </div>
              </div>
            )}
            {zoneAlarms.map((a) => {
              const c = SEVERITY[a.severity].color;
              return (
                <div key={a.id} className="rounded-lg px-3 py-2 text-xs border flex items-center justify-between gap-2" style={{ borderColor: `${c}66`, color: c, background: `${c}10` }}>
                  <div className="truncate">
                    <bdi className="font-mono">{a.alarm_code}</bdi> {pickName(lang, a.name, a.name_ar)} — {t(a.condition_active ? 'drawer.active' : 'drawer.latched')}
                  </div>
                  <button
                    onClick={() => setExplainingAlarm(a)}
                    className="px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-[#00e5ff] text-[11px] font-bold flex items-center gap-1 shrink-0 transition-colors"
                    title={t('ai.explain')}
                  >
                    <AiSparklesIcon size={12} accent="#00e5ff" />
                    <span>{t('ai.explain')}</span>
                  </button>
                </div>
              );
            })}
            {zoneAlarms.some((a) => a.alarm_code === 'ALM-036') && <MaintenanceDone zoneId={zoneId} />}
          </section>

          {/* 1.5 — Baseline Section (Normal Flow & Pressure Band) */}
          <BaselineSection
            zoneId={zoneId}
            currentFlow={zoneState?.flow_m3h}
            currentPressure={zoneState?.pressure_bar}
          />

          {/* 2 — controls */}
          <section className="panel p-4 space-y-3">
            {!canControl ? (
              <p className="text-sm text-[#849396]">{t('drawer.viewOnly')}</p>
            ) : active ? (
              <button disabled={busy} onClick={() => run('stop')} className="w-full py-3 rounded-xl border border-[#ffb4ab]/60 text-[#ffb4ab] hover:bg-[#ffb4ab]/10 font-bold flex items-center justify-center gap-2 disabled:opacity-50">
                <Square size={18} /> {t('drawer.stop')}
              </button>
            ) : (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#bac9cc]">{t('drawer.duration')}</span>
                  <bdi className="font-mono font-bold text-lg">{duration} min</bdi>
                </div>
                <div className="flex gap-2">
                  {PRESETS.filter((p) => p <= maxMin).map((p) => (
                    <button
                      key={p}
                      onClick={() => pick(p)}
                      className={`flex-1 py-1.5 rounded-lg text-sm font-mono border ${duration === p ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff]/10' : 'border-white/10 text-[#bac9cc] hover:bg-white/5'}`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                <input
                  type="range"
                  min={5}
                  max={maxMin}
                  step={5}
                  value={duration}
                  onChange={(e) => pick(Number(e.target.value))}
                  className="w-full accent-[#00e5ff]"
                  aria-label={t('drawer.duration')}
                  dir="ltr"
                />
                <div className="flex justify-between text-[10px] text-[#849396] font-mono" dir="ltr">
                  <span>5</span>
                  <span>
                    {t('drawer.usual')} {usual}
                  </span>
                  <span>max {maxMin}</span>
                </div>
                {confirming ? (
                  <div className="flex gap-2">
                    <button disabled={busy} onClick={() => run('start')} className="flex-1 py-3 rounded-xl bg-[#00e5ff] text-[#0e0e0e] font-bold flex items-center justify-center gap-2 disabled:opacity-50">
                      <Play size={18} /> {t('drawer.confirm')} <bdi>{duration} min</bdi>
                    </button>
                    <button onClick={() => setConfirming(false)} className="px-4 py-3 rounded-xl border border-white/10 text-[#bac9cc] hover:bg-white/5">
                      {t('drawer.cancel')}
                    </button>
                  </div>
                ) : (
                  <button onClick={() => setConfirming(true)} className="w-full py-3 rounded-xl border border-[#00e5ff]/60 text-[#00e5ff] hover:bg-[#00e5ff]/10 font-bold flex items-center justify-center gap-2">
                    <Play size={18} /> {t('drawer.start')}
                  </button>
                )}
              </>
            )}
            {feedback && (
              <p role="status" className={`text-xs ${feedback.kind === 'ok' ? 'text-[#00e5ff]' : 'text-[#ffb4ab]'}`}>
                {feedback.text}
              </p>
            )}
          </section>

          {/* 3 — history */}
          <section className="panel p-4">
            <div className="text-xs text-[#bac9cc] font-bold mb-3 flex justify-between items-center">
              <span>{t('drawer.history')}</span>
              <span className="flex gap-1">
                {RANGES.map((r) => (
                  <button key={r.label} onClick={() => setRange(r)} className={`px-2 py-0.5 rounded-md font-mono ${range.label === r.label ? 'bg-white/10 text-[#e5e2e1]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}>
                    {r.label}
                  </button>
                ))}
              </span>
            </div>
            <div className="h-44" dir="ltr">
              {history.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-[#849396]">{t('drawer.noHistory')}</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="g-moist" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CYAN} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={CYAN} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} minTickGap={24} />
                    <YAxis yAxisId="m" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} domain={['auto', 'auto']} width={28} />
                    <YAxis yAxisId="f" orientation="right" stroke="#ffeb3b" fontSize={10} tickLine={false} axisLine={false} width={28} />
                    <Tooltip contentStyle={{ backgroundColor: '#161618', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }} labelStyle={{ color: '#bac9cc' }} />
                    <Area yAxisId="m" type="monotone" connectNulls dataKey="moisture" name="%" stroke={CYAN} strokeWidth={2} fill="url(#g-moist)" />
                    <Area yAxisId="f" type="stepAfter" connectNulls dataKey="flow" name="m³/h" stroke="#ffeb3b" strokeWidth={1.5} fill="transparent" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          {/* 3.5 — Recent Irrigation Cycles */}
          <section className="panel p-4 space-y-3">
            <div className="text-xs text-[#bac9cc] font-bold">
              {t('zone.history.title')}
            </div>
            {recentCycles.length === 0 ? (
              <div className="text-xs text-[#849396] py-2">{t('zone.history.noCycles')}</div>
            ) : (
              <div className="space-y-2">
                {recentCycles.map((cyc) => {
                  const outcomeColor =
                    cyc.outcome === 'completed'
                      ? '#7ee787'
                      : cyc.outcome === 'skipped'
                      ? '#ffeb3b'
                      : '#ff5449';
                  const dateStr = cyc.actual_start_at
                    ? parseUtcDate(cyc.actual_start_at).toLocaleTimeString('en-GB', {
                        timeZone: 'Africa/Tripoli',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '--:--';
                  return (
                    <div
                      key={cyc.id}
                      className="p-2.5 rounded-xl bg-white/5 border border-white/5 flex items-center justify-between text-xs"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                            style={{
                              backgroundColor: `${outcomeColor}22`,
                              color: outcomeColor,
                            }}
                          >
                            {t(`outcome.${cyc.outcome}` as MsgKey)}
                          </span>
                          <span className="font-mono text-[#bac9cc]">{dateStr}</span>
                        </div>
                        <div className="text-[11px] text-[#849396] mt-1">
                          {cyc.actual_duration_min ?? cyc.planned_duration_min} min •{' '}
                          <bdi className="font-mono">{cyc.water_is_estimate ? '≈ ' : ''}{fmtNum(cyc.water_estimate_m3, 2)} m³</bdi>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* 4 — crop & hardware */}
          <section className="panel overflow-hidden">
            <img src={DETAIL_ART[crop] ?? DETAIL_ART.pomegranate} alt="" className="w-full h-36 object-cover" loading="lazy" />
            <div className="p-4 space-y-2 text-sm">
              <Row label={t('drawer.valveId')} value={<bdi className="font-mono">{valve?.valve_id ?? '—'}</bdi>} />
              <Row
                label={t('drawer.valveState')}
                value={
                  <span className="flex items-center gap-1.5" style={{ color: valve?.status === 'fault' ? SEVERITY.S3.color : valve?.status === 'open' ? CYAN : undefined }}>
                    <ValveIcon size={16} /> {t(`valve.${valve?.status ?? 'unknown'}` as MsgKey)}
                  </span>
                }
              />
              <Row label={t('drawer.flowRange')} value={<bdi className="font-mono">{config ? `${config.flow_min_m3h}–${config.flow_max_m3h} m³/h` : '—'}</bdi>} />
              <Row label={t('drawer.pressureRange')} value={<bdi className="font-mono">{config ? `${config.pressure_min_bar}–${config.pressure_max_bar} bar` : '—'}</bdi>} />
              <Row label={t('drawer.health')} value={<span style={{ color: isFault ? SEVERITY.S3.color : CYAN }}>{t(`health.${zoneState?.health ?? 'unknown'}` as MsgKey)}</span>} />
            </div>
          </section>
        </div>
      </div>

      <ExplainAlarmDrawer alarm={explainingAlarm} onClose={() => setExplainingAlarm(null)} />
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center gap-3 border-b border-white/5 pb-2 last:border-0 last:pb-0">
      <span className="text-[#849396]">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Big({ icon, label, value, unit }: { icon: React.ReactNode; label: string; value: string; unit: string }) {
  return (
    <div className="rounded-xl bg-black/30 border border-white/5 p-2.5">
      <div className="text-[#00e5ff] mb-1">{icon}</div>
      <div className="text-[11px] text-[#849396]">{label}</div>
      <div className="font-mono font-bold text-xl leading-tight" dir="ltr">
        {value}
        <span className="text-[10px] text-[#849396] ms-1">{unit}</span>
      </div>
    </div>
  );
}
