import { useEffect, useState } from 'react';
import EmptyState from '../components/EmptyState';
import MaintenanceDone from '../components/MaintenanceDone';
import { AlertTriangle, CheckCircle, ChevronDown, ChevronRight, RotateCcw } from 'lucide-react';
import type { Alarm, AlarmSeverity } from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import { useFarmStore } from '../store/farm';
import { useAuth } from '../lib/auth';
import { apiFetch } from '../lib/api';
import { SEVERITY, availableActions, sortAlarms } from '../lib/alarms';
import { pickName, useT, type MsgKey } from '../lib/i18n';

const NO_ALARMS: Alarm[] = [];
const ZONE_NAME = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));

type View = 'active' | 'history';
type SevFilter = 'all' | AlarmSeverity;

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Tripoli',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  })
    .format(d)
    .replace(',', '');
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
  const { t, lang } = useT();
  const sevLabel = (sv: AlarmSeverity) => (lang === 'ar' ? SEVERITY[sv].labelAr : SEVERITY[sv].label);
  const stateText = (a: Alarm) =>
    a.status === 'cleared'
      ? t('al.st.cleared')
      : `${t(a.condition_active ? 'al.st.active' : 'al.st.latched')} · ${t(a.status === 'active_acked' ? 'al.st.acked' : 'al.st.unacked')}`;

  useEffect(() => {
    if (view !== 'history') return;
    let live = true;
    apiFetch<Alarm[]>('/api/v1/alarms?view=history&limit=200')
      .then((rows) => live && setHistory(rows))
      .catch(() => live && setError(t('al.loadError')));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
          <h1 className="text-2xl font-bold text-[#e5e2e1] flex items-center gap-3">
            <AlertTriangle className="text-[#ffb4ab]" size={26} />
            {t('al.title')}
          </h1>
          <p className="text-[#849396] mt-1 text-sm">
            {counts.map(({ s, n }) => (
              <span key={s} className="me-4" style={{ color: n ? SEVERITY[s].color : undefined }}>
                {sevLabel(s)} {n}
              </span>
            ))}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-sm">
          {(['active', 'history'] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-4 py-2 border rounded-lg ${view === v ? 'bg-[#353534] border-[#849396] text-[#e5e2e1]' : 'border-[#353534] text-[#849396] hover:bg-[#1c1b1b]'}`}
            >
              {t(`al.view.${v}` as MsgKey)}
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
              {f === 'all' ? t('al.all') : sevLabel(f)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div role="alert" className="p-3 border border-[#ffb4ab] text-[#ffb4ab] font-mono text-sm rounded">
          {error}
        </div>
      )}

      <div className="panel flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="hidden md:grid grid-cols-12 gap-4 p-4 border-b border-[#353534] bg-[#1c1b1b] text-[#bac9cc] text-xs font-bold">
          <div className="col-span-2">{t('al.triggered')}</div>
          <div className="col-span-1">{t('al.severity')}</div>
          <div className="col-span-4">{t('al.alarm')}</div>
          <div className="col-span-2">{t('al.source')}</div>
          <div className="col-span-2">{t('al.state')}</div>
          <div className="col-span-1 text-end">{t('al.actions')}</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {rows.map((alarm) => {
            const meta = SEVERITY[alarm.severity];
            const actions = availableActions(alarm);
            const open = expanded === alarm.id;
            return (
              <div key={alarm.id} className="border-b border-[#353534]">
                <div
                  className="grid grid-cols-2 md:grid-cols-12 gap-2 md:gap-4 p-4 text-sm items-center hover:bg-[#1c1b1b]/50 transition-colors cursor-pointer"
                  onClick={() => setExpanded(open ? null : alarm.id)}
                >
                  <div className="md:col-span-2 text-[#849396] font-mono text-xs flex items-center gap-2" dir="ltr">
                    {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {fmtTime(alarm.triggered_at)}
                  </div>
                  <div className="md:col-span-1 text-end md:text-start">
                    <span
                      className="px-2 py-1 rounded text-xs font-bold border whitespace-nowrap"
                      style={{ color: meta.color, borderColor: `${meta.color}55`, backgroundColor: `${meta.color}15` }}
                    >
                      {sevLabel(alarm.severity)}
                    </span>
                  </div>
                  <div className="col-span-2 md:col-span-4 min-w-0">
                    <div className="text-[#e5e2e1] truncate">
                      <span className="font-mono text-[#849396] me-2" dir="ltr">{alarm.alarm_code}</span>
                      {pickName(lang, alarm.name, alarm.name_ar)}
                    </div>
                  </div>
                  <div className="md:col-span-2 text-xs text-[#e5e2e1] truncate">
                    {alarm.zone_id && ZONE_NAME[alarm.zone_id] ? (
                      pickName(lang, ZONE_NAME[alarm.zone_id].name, ZONE_NAME[alarm.zone_id].name_ar)
                    ) : (
                      <bdi className="font-mono">{alarm.zone_id ?? alarm.device_id ?? t('al.system')}</bdi>
                    )}
                  </div>
                  <div className="md:col-span-2">
                    <span
                      className={`text-xs font-bold ${alarm.status === 'active_unacked' && alarm.condition_active ? 'animate-pulse' : ''}`}
                      style={{ color: alarm.status === 'cleared' ? '#849396' : meta.color }}
                    >
                      {stateText(alarm)}
                    </span>
                  </div>
                  <div className="md:col-span-1 flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                    {actions.includes('ack') && can('owner_admin', 'operator') && (
                      <button
                        onClick={() => act(alarm, 'ack')}
                        className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#ffeb3b] text-[#ffeb3b] transition-colors"
                        title={t('al.ack')}
                        aria-label={`${t('al.ack')} ${alarm.alarm_code}`}
                      >
                        <CheckCircle size={16} />
                      </button>
                    )}
                    {actions.includes('reset') && can('owner_admin') && (
                      <button
                        onClick={() => act(alarm, 'reset')}
                        className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#00e5ff] text-[#00e5ff] transition-colors"
                        title={t('al.reset')}
                        aria-label={`${t('al.reset')} ${alarm.alarm_code}`}
                      >
                        <RotateCcw size={16} />
                      </button>
                    )}
                  </div>
                </div>

                {open && (
                  <div className="px-4 md:px-12 pb-5 space-y-4 text-sm">
                    {(lang === 'ar' ? ['ar', 'en'] : ['en', 'ar']).map((l, i) => (
                      <div key={l} dir={l === 'ar' ? 'rtl' : 'ltr'} className={`space-y-2 ${i ? 'opacity-70 border-t border-[#353534] pt-3' : ''}`}>
                        <p className="text-[#e5e2e1]">{l === 'ar' ? alarm.message_ar : alarm.message_en}</p>
                        <p className="text-[#bac9cc]">
                          <span className="text-[#00e5ff] text-xs font-bold me-2">{l === 'ar' ? 'الإجراء' : 'ACTION'}</span>
                          {l === 'ar' ? alarm.guidance_ar : alarm.guidance_en}
                        </p>
                      </div>
                    ))}
                    {alarm.alarm_code === 'ALM-036' && alarm.zone_id && alarm.status !== 'cleared' && <MaintenanceDone zoneId={alarm.zone_id} />}
                    <p className="text-xs text-[#849396] flex flex-wrap gap-x-3 gap-y-1">
                      {alarm.current_value != null && <span>{t('al.value')} <bdi className="font-mono">{alarm.current_value}</bdi></span>}
                      {alarm.threshold_value != null && <span>{t('al.threshold')} <bdi className="font-mono">{alarm.threshold_value}</bdi></span>}
                      <span>{t(`actor.${alarm.source_layer}` as MsgKey)}</span>
                      {alarm.requires_manual_reset && <span>{t('al.manualReset')}</span>}
                      <span>{t('al.acked')} <bdi className="font-mono">{fmtTime(alarm.acknowledged_at)}</bdi></span>
                      <span>{t('al.cleared')} <bdi className="font-mono">{fmtTime(alarm.cleared_at)}</bdi></span>
                      <span>{t('al.resetAt')} <bdi className="font-mono">{fmtTime(alarm.reset_at)}</bdi></span>
                    </p>
                  </div>
                )}
              </div>
            );
          })}
          {rows.length === 0 && (
            <EmptyState art="alarms" text={view === 'active' ? t('empty.alarms') : t('al.noHistory')} />
          )}
        </div>
      </div>
    </div>
  );
}
