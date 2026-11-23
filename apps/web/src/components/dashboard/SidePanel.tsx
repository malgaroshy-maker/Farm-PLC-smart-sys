import { useState } from 'react';
import { ZONE_BY_ID } from '../../lib/zones';
import { Link } from 'react-router-dom';
import { Area, AreaChart, Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Alarm, FarmMapState, TelemetrySeries } from '@algaroshy/contracts';
import { usePoll } from '../../lib/poll';
import { SEVERITY, sortAlarms } from '../../lib/alarms';
import { fmtNum, pickName, useT, type MsgKey } from '../../lib/i18n';
import { AlarmIcon, PumpIcon, TankIcon } from '../icons/FarmIcons';
import { parseUtcDate, useClockStore } from '../../lib/clock';

const CYAN = '#00e5ff';
const SEED = ZONE_BY_ID; // live catalog (Settings → Zones & equipment)
const tip = {
  contentStyle: { background: '#161618', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 12 },
  labelStyle: { color: '#bac9cc' },
};

function hhmm(ts: string) {
  return parseUtcDate(ts).toLocaleTimeString('en-GB', { timeZone: 'Africa/Tripoli', hour: '2-digit', minute: '2-digit' });
}


// ── tank ────────────────────────────────────────────────────────────────

export function TankCard({ state }: { state: FarmMapState | null }) {
  const { t } = useT();
  const pct = state?.tank_level_pct ?? 0;
  const color = pct < 10 ? SEVERITY.S3.color : pct < 25 ? SEVERITY.S1.color : CYAN;
  const refilling = state?.pumps.find((p) => p.pump_id === 'pump_well_01')?.state === 'running';
  return (
    <div className="panel p-4 flex items-center gap-4">
      <div className="relative w-16 h-24 rounded-xl border border-white/15 bg-[#0e0e0e] overflow-hidden shrink-0" aria-label={`${fmtNum(pct, 1)}%`}>
        <div className="absolute inset-x-0 bottom-0 transition-all duration-1000" style={{ height: `${Math.min(100, pct)}%`, background: `linear-gradient(180deg, ${color}aa, ${color}33)` }}>
          <svg className="absolute -top-2 left-0 w-[200%] h-3 tank-wave" viewBox="0 0 120 10" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 5 Q 7.5 0 15 5 T 30 5 T 45 5 T 60 5 T 75 5 T 90 5 T 105 5 T 120 5 V10 H0Z" fill={`${color}aa`} />
          </svg>
        </div>
      </div>
      <div className="min-w-0">
        <div className="text-xs text-[#bac9cc] font-bold flex items-center gap-1.5">
          <TankIcon size={16} /> {t('kpi.tank')}
        </div>
        <div className="text-3xl font-bold font-mono" style={{ color }} dir="ltr">
          {fmtNum(pct, 1)}%
        </div>
        <div className="text-xs text-[#849396]">{refilling ? t('dash.refilling') : t('dash.tankIdle')}</div>
      </div>
    </div>
  );
}

// ── pumps ───────────────────────────────────────────────────────────────

export function PumpsCard({ state }: { state: FarmMapState | null }) {
  const { t, lang } = useT();
  const names: Record<string, [string, string]> = {
    pump_booster_01: ['Booster pump', 'مضخة التعزيز'],
    pump_well_01: ['Well pump', 'مضخة البئر'],
  };
  return (
    <div className="panel p-4 space-y-2">
      <div className="text-xs text-[#bac9cc] font-bold">{t('eq.pumps')}</div>
      {(state?.pumps ?? []).map((p) => {
        const color = p.fault || p.state === 'failed_start' ? SEVERITY.S3.color : p.state === 'running' ? CYAN : '#849396';
        const [en, ar] = names[p.pump_id] ?? [p.pump_id, p.pump_id];
        return (
          <div key={p.pump_id} className="flex items-center gap-3">
            <span style={{ color }} className={p.state === 'running' ? 'spin-slow' : ''}>
              <PumpIcon size={22} accent={color} />
            </span>
            <span className="flex-1 text-sm">{lang === 'ar' ? ar : en}</span>
            <span className="text-xs font-bold" style={{ color }}>
              {t(`pump.${p.state}` as MsgKey)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── alarms ──────────────────────────────────────────────────────────────

export function AlarmsCard({ alarms }: { alarms: Alarm[] }) {
  const { t, lang } = useT();
  const top = sortAlarms(alarms).slice(0, 4);
  return (
    <div className="panel p-4 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-xs text-[#bac9cc] font-bold flex items-center gap-1.5">
          <AlarmIcon size={16} /> {t('nav.alarms')}
        </span>
        <Link to="/alarms" className="text-xs text-[#00e5ff] hover:underline">
          {t('dash.all')} <bdi className="font-mono">({alarms.length})</bdi>
        </Link>
      </div>
      {top.length === 0 ? (
        <div className="text-sm text-[#7ee787] py-2">✓ {t('al.noActive')}</div>
      ) : (
        top.map((a) => (
          <Link key={a.id} to="/alarms" className="flex items-start gap-2 text-sm rounded-lg p-1.5 -m-1.5 hover:bg-white/5">
            <span className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{ background: SEVERITY[a.severity].color }} />
            <span className="min-w-0">
              <span className="block truncate">{pickName(lang, a.name, a.name_ar)}</span>
              <span className="text-[11px] text-[#849396]">
                <bdi className="font-mono">{a.alarm_code}</bdi> · {a.zone_id ? pickName(lang, SEED[a.zone_id]?.name, SEED[a.zone_id]?.name_ar) : t('al.system')}
              </span>
            </span>
          </Link>
        ))
      )}
    </div>
  );
}

// ── trends ──────────────────────────────────────────────────────────────

type Trend = 'tank' | 'flow' | 'water';

export function TrendsCard() {
  const { t, lang } = useT();
  const [tab, setTab] = useState<Trend>('tank');
  const speed = useClockStore((s) => s.speed);
  const fast = speed >= 60 ? 3_000 : speed >= 10 ? 8_000 : 30_000;
  const fastLong = speed >= 60 ? 5_000 : speed >= 10 ? 15_000 : 60_000;
  const tank = usePoll<TelemetrySeries>('/api/v1/telemetry/series?metric_key=tank_level_pct&minutes=1440&points=72', fastLong);
  const flow = usePoll<TelemetrySeries>('/api/v1/telemetry/series?metric_key=main_flow_m3h&minutes=60&points=60', fast);
  const pres = usePoll<TelemetrySeries>('/api/v1/telemetry/series?metric_key=main_pressure_bar&minutes=60&points=60', fast);
  const water = usePoll<{ zones: { zone_id: string; m3: number }[]; total_m3: number }>('/api/v1/telemetry/water-today', fast);

  const flowRows = (flow?.points ?? []).map((p, i) => ({ time: hhmm(p.ts), flow: p.value, pressure: pres?.points[i]?.value }));
  const waterRows = (water?.zones ?? [])
    .filter((z) => z.m3 > 0)
    .map((z) => ({ name: pickName(lang, SEED[z.zone_id]?.name, SEED[z.zone_id]?.name_ar), m3: z.m3 }));

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex gap-1 text-xs">
        {(['tank', 'flow', 'water'] as Trend[]).map((k) => (
          <button key={k} onClick={() => setTab(k)} className={`px-2.5 py-1 rounded-lg ${tab === k ? 'bg-white/10 text-[#e5e2e1]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}>
            {t(`dash.trend.${k}` as MsgKey)}
          </button>
        ))}
      </div>
      <div className="h-40" dir="ltr">
        {tab === 'tank' && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={(tank?.points ?? []).map((p) => ({ time: hhmm(p.ts), v: p.value }))}>
              <defs>
                <linearGradient id="g-tank" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CYAN} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={CYAN} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
              <YAxis domain={[0, 100]} stroke="#849396" fontSize={10} tickLine={false} axisLine={false} width={28} />
              <Tooltip {...tip} />
              <Area type="monotone" dataKey="v" name="%" stroke={CYAN} strokeWidth={2} fill="url(#g-tank)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
        {tab === 'flow' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={flowRows}>
              <XAxis dataKey="time" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
              <YAxis yAxisId="f" stroke={CYAN} fontSize={10} tickLine={false} axisLine={false} width={28} />
              <YAxis yAxisId="p" orientation="right" stroke="#ffeb3b" fontSize={10} tickLine={false} axisLine={false} width={28} />
              <Tooltip {...tip} />
              <Line yAxisId="f" type="monotone" dataKey="flow" name="m³/h" stroke={CYAN} strokeWidth={2} dot={false} />
              <Line yAxisId="p" type="monotone" dataKey="pressure" name="bar" stroke="#ffeb3b" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
        {tab === 'water' &&
          (waterRows.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-[#849396]">{t('dash.noWater')}</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={waterRows} layout="vertical" margin={{ left: 8 }}>
                <XAxis type="number" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" interval={0} stroke="#bac9cc" fontSize={10} tickLine={false} axisLine={false} width={80} />
                <Tooltip {...tip} />
                <Bar dataKey="m3" name="m³" fill={CYAN} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ))}
      </div>
      {tab === 'water' && water && (
        <div className="text-xs text-[#849396]">
          {t('dash.waterTotal')}: <bdi className="font-mono text-[#e5e2e1]">{fmtNum(water.total_m3, 2)} m³</bdi>
        </div>
      )}
    </div>
  );
}

// ── phone status card ───────────────────────────────────────────────────

export function StatusCard({ state }: { state: FarmMapState | null }) {
  const { t } = useT();
  const alarms = state?.active_alarms ?? [];
  const worst = sortAlarms(alarms)[0];
  const running = (state?.zones ?? []).filter((z) => z.state === 'running').length;
  const color = worst ? SEVERITY[worst.severity].color : running ? CYAN : '#7ee787';
  const title = worst ? `${alarms.length} ${t('header.alarms')}` : running ? t('dash.irrigating') : t('dash.allOk');
  return (
    <div className="panel p-4 flex items-center gap-4" style={{ borderColor: `${color}55` }}>
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0" style={{ background: `${color}1f`, color }}>
        {worst ? <AlarmIcon size={28} accent={color} /> : <TankIcon size={28} accent={color} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-lg font-bold" style={{ color }}>
          {title}
        </div>
        <div className="text-xs text-[#849396]">
          {t('kpi.zonesRunning')}: <bdi className="font-mono">{running} / 12</bdi> · {t('kpi.tank')}: <bdi className="font-mono">{fmtNum(state?.tank_level_pct, 0)}%</bdi>
        </div>
      </div>
      <div className="flex flex-col gap-1.5 text-xs shrink-0">
        <Link to="/alarms" className="px-3 py-1.5 rounded-lg bg-white/5 text-center">
          {t('nav.alarms')}
        </Link>
        <Link to="/zones" className="px-3 py-1.5 rounded-lg bg-white/5 text-center">
          {t('nav.zones')}
        </Link>
      </div>
    </div>
  );
}
