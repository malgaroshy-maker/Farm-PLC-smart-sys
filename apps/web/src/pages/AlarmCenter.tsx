import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle, ChevronDown, ChevronRight, RotateCcw } from 'lucide-react';
import type { Alarm, AlarmSeverity } from '@algaroshy/contracts';
import { useFarmStore } from '../store/farm';
import { useAuth } from '../lib/auth';
import { apiFetch } from '../lib/api';
import { SEVERITY, availableActions, describeState, sortAlarms } from '../lib/alarms';

const NO_ALARMS: Alarm[] = [];

type View = 'active' | 'history';
type SevFilter = 'all' | AlarmSeverity;

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.toISOString().slice(0, 10)} ${d.toISOString().slice(11, 19)}`;
}

export default function AlarmCenter() {
  const [view, setView] = useState<View>('active');
  const [sev, setSev] = useState<SevFilter>('all');
  const [history, setHistory] = useState<Alarm[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeRaw = useFarmStore((s) => s.state?.active_alarms);
  const active = activeRaw ?? NO_ALARMS;
  const alarmAction = useFarmStore((s) => s.alarmAction);
  const { can } = useAuth();

  useEffect(() => {
    if (view !== 'history') return;
    let live = true;
    apiFetch<Alarm[]>('/api/v1/alarms?view=history&limit=200')
      .then((rows) => live && setHistory(rows))
      .catch(() => live && setError('Could not load history'));
    return () => {
      live = false;
    };
  }, [view, active.length]);

  const rows = (view === 'active' ? sortAlarms(active) : history).filter(
    (a) => sev === 'all' || a.severity === sev,
  );

  const act = async (alarm: Alarm, action: 'ack' | 'reset') => {
    setError(null);
    const err = await alarmAction(alarm.id, action);
    if (err) setError(`${alarm.alarm_code}: ${err}`);
  };

  const counts = (['S3', 'S2', 'S1', 'S0'] as AlarmSeverity[]).map((s) => ({
    s,
    n: active.filter((a) => a.severity === s).length,
  }));

  return (
    <div className="space-y-6 h-full flex flex-col font-sans">
      <div className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1] tracking-wider flex items-center gap-3">
            <AlertTriangle className="text-[#ffb4ab]" size={28} />
            ALARM CENTER
          </h1>
          <p className="text-[#849396] mt-1 font-mono text-sm">
            {counts.map(({ s, n }) => (
              <span key={s} className="mr-4" style={{ color: n ? SEVERITY[s].color : undefined }}>
                {SEVERITY[s].label} {n}
              </span>
            ))}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 font-mono text-sm">
          {(['active', 'history'] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-4 py-2 border rounded uppercase ${view === v ? 'bg-[#353534] border-[#849396] text-[#e5e2e1]' : 'border-[#353534] text-[#849396] hover:bg-[#1c1b1b]'}`}
            >
              {v}
            </button>
          ))}
          <span className="w-px bg-[#353534] mx-1" />
          {(['all', 'S3', 'S2', 'S1', 'S0'] as SevFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setSev(f)}
              className={`px-3 py-2 border rounded ${sev === f ? 'bg-[#353534] border-[#849396]' : 'border-[#353534] hover:bg-[#1c1b1b]'}`}
              style={{ color: f === 'all' ? '#e5e2e1' : SEVERITY[f].color }}
            >
              {f === 'all' ? 'ALL' : SEVERITY[f].label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div role="alert" className="p-3 border border-[#ffb4ab] text-[#ffb4ab] font-mono text-sm rounded">
          {error}
        </div>
      )}

      <div className="flex-1 min-h-0 bg-[#0e0e0e] border border-[#353534] rounded-lg overflow-hidden flex flex-col">
        <div className="grid grid-cols-12 gap-4 p-4 border-b border-[#353534] bg-[#1c1b1b] text-[#bac9cc] font-mono text-xs tracking-widest font-bold">
          <div className="col-span-2">TRIGGERED</div>
          <div className="col-span-1">SEVERITY</div>
          <div className="col-span-4">ALARM</div>
          <div className="col-span-2">SOURCE</div>
          <div className="col-span-2">STATE</div>
          <div className="col-span-1 text-right">ACTIONS</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {rows.map((alarm) => {
            const meta = SEVERITY[alarm.severity];
            const actions = availableActions(alarm);
            const open = expanded === alarm.id;
            return (
              <div key={alarm.id} className="border-b border-[#353534]">
                <div
                  className="grid grid-cols-12 gap-4 p-4 text-sm items-center hover:bg-[#1c1b1b]/50 transition-colors cursor-pointer"
                  onClick={() => setExpanded(open ? null : alarm.id)}
                >
                  <div className="col-span-2 text-[#849396] font-mono text-xs flex items-center gap-2">
                    {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {fmtTime(alarm.triggered_at)}
                  </div>
                  <div className="col-span-1">
                    <span
                      className="px-2 py-1 rounded text-xs font-bold font-mono tracking-wider border"
                      style={{ color: meta.color, borderColor: `${meta.color}55`, backgroundColor: `${meta.color}15` }}
                    >
                      {meta.label}
                    </span>
                  </div>
                  <div className="col-span-4 min-w-0">
                    <div className="text-[#e5e2e1] truncate">
                      <span className="font-mono text-[#849396] mr-2">{alarm.alarm_code}</span>
                      {alarm.name}
                    </div>
                    {alarm.name_ar && (
                      <div className="text-xs text-[#bac9cc] truncate" dir="rtl">{alarm.name_ar}</div>
                    )}
                  </div>
                  <div className="col-span-2 font-mono text-xs text-[#e5e2e1] truncate">
                    {alarm.zone_id ?? alarm.device_id ?? 'SYSTEM'}
                  </div>
                  <div className="col-span-2">
                    <span
                      className={`text-xs font-mono font-bold tracking-wider ${alarm.status === 'active_unacked' && alarm.condition_active ? 'animate-pulse' : ''}`}
                      style={{ color: alarm.status === 'cleared' ? '#849396' : meta.color }}
                    >
                      {describeState(alarm)}
                    </span>
                  </div>
                  <div className="col-span-1 flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                    {actions.includes('ack') && can('owner_admin', 'operator') && (
                      <button
                        onClick={() => act(alarm, 'ack')}
                        className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#ffeb3b] text-[#ffeb3b] transition-colors"
                        title="Acknowledge"
                        aria-label={`Acknowledge ${alarm.alarm_code}`}
                      >
                        <CheckCircle size={16} />
                      </button>
                    )}
                    {actions.includes('reset') && can('owner_admin') && (
                      <button
                        onClick={() => act(alarm, 'reset')}
                        className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#00e5ff] text-[#00e5ff] transition-colors"
                        title="Reset (condition has returned to normal)"
                        aria-label={`Reset ${alarm.alarm_code}`}
                      >
                        <RotateCcw size={16} />
                      </button>
                    )}
                  </div>
                </div>

                {open && (
                  <div className="px-12 pb-5 grid md:grid-cols-2 gap-6 text-sm">
                    <div className="space-y-2">
                      <p className="text-[#e5e2e1]">{alarm.message_en}</p>
                      <p className="text-[#bac9cc]"><span className="text-[#00e5ff] font-mono text-xs mr-2">ACTION</span>{alarm.guidance_en}</p>
                      <p className="font-mono text-xs text-[#849396]">
                        {alarm.current_value != null && <>value {alarm.current_value} </>}
                        {alarm.threshold_value != null && <>· threshold {alarm.threshold_value} </>}
                        · source {alarm.source_layer}
                        {alarm.requires_manual_reset && ' · manual reset required'}
                      </p>
                      <p className="font-mono text-xs text-[#849396]">
                        acked {fmtTime(alarm.acknowledged_at)} · cleared {fmtTime(alarm.cleared_at)} · reset {fmtTime(alarm.reset_at)}
                      </p>
                    </div>
                    <div className="space-y-2" dir="rtl">
                      <p className="text-[#e5e2e1]">{alarm.message_ar}</p>
                      <p className="text-[#bac9cc]"><span className="text-[#00e5ff] text-xs ml-2">الإجراء</span>{alarm.guidance_ar}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {rows.length === 0 && (
            <div className="p-8 text-center text-[#849396] font-mono">
              {view === 'active' ? 'NO ACTIVE ALARMS' : 'NO ALARMS IN HISTORY'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
