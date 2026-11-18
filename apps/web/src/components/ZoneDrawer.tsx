import { useEffect, useState } from 'react';
import { X, Activity, Droplet, Gauge, Clock, Play, Square } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { TelemetrySeries } from '@algaroshy/contracts';

import type { ZoneLiveState } from '../hooks/useFarmConnector';
import type { CommandOutcome } from '../store/farm';
import { useFarmStore } from '../store/farm';
import { useAuth } from '../lib/auth';
import { apiFetch } from '../lib/api';
import { SEVERITY } from '../lib/alarms';

interface ZoneDrawerProps {
  zoneId: string | null;
  zoneState?: ZoneLiveState;
  onClose: () => void;
  onCommand?: (action: 'start' | 'stop', targetId: string) => Promise<CommandOutcome>;
}

type Feedback = { kind: 'ok' | 'error'; text: string } | null;
type ChartRow = { time: string; moisture?: number; flow?: number };

const RANGES = [
  { label: '1H', minutes: 60 },
  { label: '6H', minutes: 360 },
  { label: '24H', minutes: 1440 },
];

function hhmmss(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60].map((n) => String(n).padStart(2, '0')).join(':');
}

function useZoneHistory(zoneId: string, minutes: number): ChartRow[] {
  const [rows, setRows] = useState<ChartRow[]>([]);
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
        const label = (ts: string) => new Date(ts).toTimeString().slice(0, 5);
        m.points.forEach((p) => byTs.set(p.ts, { time: label(p.ts), moisture: p.value }));
        f.points.forEach((p) => byTs.set(p.ts, { ...(byTs.get(p.ts) ?? { time: label(p.ts) }), flow: p.value }));
        if (live) setRows([...byTs.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, r]) => r));
      } catch {
        if (live) setRows([]);
      }
    };
    void load();
    const id = setInterval(load, 15000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [zoneId, minutes]);
  return rows;
}

export default function ZoneDrawer(props: ZoneDrawerProps) {
  if (!props.zoneId) return null;
  // Keyed by zone so feedback resets when another zone is opened.
  return <ZoneDrawerBody key={props.zoneId} {...props} zoneId={props.zoneId} />;
}

function ZoneDrawerBody({ zoneId, zoneState, onClose, onCommand }: ZoneDrawerProps & { zoneId: string }) {
  const { can } = useAuth();
  const canControl = can('owner_admin', 'operator');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [range, setRange] = useState(RANGES[0]);
  const history = useZoneHistory(zoneId, range.minutes);
  const valve = useFarmStore((s) => s.state?.valves.find((v) => v.zone_id === zoneId));
  const allAlarms = useFarmStore((s) => s.state?.active_alarms);
  const zoneAlarms = (allAlarms ?? []).filter((a) => a.zone_id === zoneId);

  const run = async (action: 'start' | 'stop') => {
    if (!onCommand) return;
    setBusy(true);
    setFeedback(null);
    const res = await onCommand(action, zoneId);
    setBusy(false);
    setFeedback(
      res.ok
        ? { kind: 'ok', text: `${action === 'start' ? 'Start' : 'Stop'} command accepted` }
        : { kind: 'error', text: `Blocked: ${res.message}` },
    );
  };

  const state = zoneState?.state ?? 'unknown';
  const isRunning = state === 'running';
  const isFault = state === 'faulted' || zoneState?.health === 'critical';
  const stateLabel = state.replace(/_/g, ' ').toUpperCase();
  const moisture = zoneState?.moisture_pct != null ? zoneState.moisture_pct.toFixed(1) : '--';
  const pressure = zoneState?.pressure_bar ? zoneState.pressure_bar.toFixed(2) : '0.00';
  const flow = zoneState?.flow_m3h ? Math.round(zoneState.flow_m3h * (1000 / 60)) : 0; // L/min
  const target = zoneState?.target_runtime_sec ?? 0;
  const runtime = zoneState?.runtime_sec ?? 0;
  const progress = target > 0 ? Math.min(100, (runtime / target) * 100) : 0;
  const badgeColor = isFault ? '#ffb4ab' : isRunning ? '#00e5ff' : '#849396';

  return (
    <>
      <div className="fixed inset-0 bg-[#0e0e0e]/80 backdrop-blur-sm z-40 transition-opacity" onClick={onClose} />

      <div className="fixed top-0 right-0 h-full w-[450px] max-w-full bg-[#1c1b1b] border-l border-[#353534] shadow-2xl z-50 flex flex-col font-sans text-[#e5e2e1]">
        {/* Header */}
        <div className="p-6 border-b border-[#353534] flex justify-between items-start bg-[#0e0e0e]">
          <div>
            <h2 className="text-2xl font-bold text-[#00e5ff] uppercase tracking-widest font-mono">
              {zoneId.replace('zone_', '').replace(/_/g, ' ')}
            </h2>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span
                className="px-2 py-0.5 rounded text-xs font-bold font-mono tracking-wider border"
                style={{ color: badgeColor, borderColor: `${badgeColor}55`, backgroundColor: `${badgeColor}15` }}
              >
                STATE: {stateLabel}
              </span>
              <span className="text-xs text-[#849396] font-mono border-l border-[#353534] pl-2">
                SOURCE: {zoneState?.source_mode === 'well_direct' ? 'DIRECT WELL' : zoneState?.source_mode ? 'TANK' : '—'}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-[#849396] bg-[#1c1b1b] hover:bg-[#ffb4ab] hover:text-[#410002] p-2 rounded transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Actions */}
          <div className="border-b border-[#353534] pb-6 space-y-3">
            {canControl ? (
              <div className="flex gap-4">
                <button
                  disabled={busy}
                  onClick={() => run('start')}
                  className="flex-1 bg-[#1c1b1b] hover:bg-[#353534] disabled:opacity-50 border border-[#353534] hover:border-[#00e5ff] text-[#00e5ff] py-3 rounded flex items-center justify-center gap-2 font-bold font-mono tracking-wider transition-colors">
                  <Play size={18} /> START CYCLE
                </button>
                <button
                  disabled={busy}
                  onClick={() => run('stop')}
                  className="flex-1 bg-[#1c1b1b] hover:bg-[#353534] disabled:opacity-50 border border-[#353534] hover:border-[#ffb4ab] text-[#ffb4ab] py-3 rounded flex items-center justify-center gap-2 font-bold font-mono tracking-wider transition-colors">
                  <Square size={18} /> STOP ZONE
                </button>
              </div>
            ) : (
              <p className="text-xs font-mono text-[#849396]">VIEW ONLY — your role cannot issue commands.</p>
            )}
            {feedback && (
              <p role="status" className={`text-xs font-mono ${feedback.kind === 'ok' ? 'text-[#00e5ff]' : 'text-[#ffb4ab]'}`}>
                {feedback.text}
              </p>
            )}
            {target > 0 && (state === 'running' || state === 'stopping') && (
              <div>
                <div className="flex justify-between text-xs font-mono text-[#849396] mb-1">
                  <span>CYCLE {hhmmss(runtime)}</span>
                  <span>{hhmmss(target)}</span>
                </div>
                <div className="h-1.5 bg-[#353534] rounded overflow-hidden">
                  <div className="h-full bg-[#00e5ff] transition-all" style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
          </div>

          {/* Zone alarms */}
          {zoneAlarms.length > 0 && (
            <div className="space-y-2">
              {zoneAlarms.map((a) => (
                <div key={a.id} className="p-3 rounded border text-xs font-mono" style={{ borderColor: SEVERITY[a.severity].color, color: SEVERITY[a.severity].color }}>
                  {a.alarm_code} {a.name} — {a.condition_active ? 'ACTIVE' : 'LATCHED'}
                </div>
              ))}
            </div>
          )}

          {/* Live metrics */}
          <div className="grid grid-cols-2 gap-4">
            <MetricCard icon={<Droplet />} label="MOISTURE" value={moisture} unit="%" />
            <MetricCard icon={<Gauge />} label="PRESSURE" value={pressure} unit="BAR" />
            <MetricCard icon={<Activity />} label="FLOW RATE" value={flow} unit="L/MIN" />
            <MetricCard icon={<Clock />} label="RUNTIME" value={hhmmss(runtime)} />
          </div>

          {/* History */}
          <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4">
            <h3 className="text-xs text-[#bac9cc] font-bold font-mono tracking-widest mb-4 flex justify-between items-center">
              <span>MOISTURE % · FLOW m³/h</span>
              <span className="flex gap-1">
                {RANGES.map((r) => (
                  <button
                    key={r.label}
                    onClick={() => setRange(r)}
                    className={`px-2 py-0.5 rounded ${range.label === r.label ? 'bg-[#353534] text-[#e5e2e1]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}
                  >
                    {r.label}
                  </button>
                ))}
              </span>
            </h3>
            <div className="h-48 w-full">
              {history.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs font-mono text-[#849396]">
                  NO HISTORY YET — data is sampled every 10 s
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="colorMoisture" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00e5ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} minTickGap={24} />
                    <YAxis yAxisId="m" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                    <YAxis yAxisId="f" orientation="right" stroke="#ffeb3b" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1c1b1b', border: '1px solid #353534', borderRadius: '4px' }}
                      labelStyle={{ color: '#bac9cc' }}
                    />
                    <Area yAxisId="m" type="monotone" dataKey="moisture" name="Moisture %" stroke="#00e5ff" strokeWidth={2} fill="url(#colorMoisture)" />
                    <Area yAxisId="f" type="stepAfter" dataKey="flow" name="Flow m³/h" stroke="#ffeb3b" strokeWidth={1.5} fill="transparent" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Hardware */}
          <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4">
            <h3 className="text-xs text-[#bac9cc] font-bold font-mono tracking-widest mb-4">HARDWARE STATUS</h3>
            <div className="space-y-3 font-mono text-sm">
              <Row label="VALVE ID" value={valve?.valve_id ?? '—'} />
              <Row
                label="VALVE STATE"
                value={(valve?.status ?? 'unknown').toUpperCase()}
                color={valve?.status === 'fault' ? '#ffb4ab' : valve?.status === 'open' ? '#00e5ff' : undefined}
              />
              <Row
                label="HEALTH"
                value={(zoneState?.health ?? 'unknown').toUpperCase()}
                color={isFault ? '#ffb4ab' : '#00e5ff'}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between border-b border-[#353534] pb-2 last:border-0">
      <span className="text-[#849396]">{label}</span>
      <span style={{ color: color ?? '#e5e2e1' }}>{value}</span>
    </div>
  );
}

function MetricCard({ icon, label, value, unit = '' }: { icon: React.ReactNode; label: string; value: string | number; unit?: string }) {
  return (
    <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4 flex flex-col pt-5 relative overflow-hidden">
      <div className="absolute left-0 top-0 w-1 h-full bg-[#00e5ff] opacity-50" />
      <div className="text-[#00e5ff] mb-3 bg-[#1c1b1b] p-2 rounded self-start border border-[#353534]">{icon}</div>
      <div className="text-xs text-[#849396] font-bold font-mono mb-1 tracking-wider uppercase">{label}</div>
      <div className="text-2xl font-bold font-mono text-[#e5e2e1]">
        {value} <span className="text-sm text-[#bac9cc]">{unit}</span>
      </div>
    </div>
  );
}
