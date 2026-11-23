import { useMemo, useState } from 'react';
import EmptyState, { ErrorState, LoadingState } from '../components/EmptyState';
import { useLoad } from '../lib/useLoad';
import { ZonesIcon } from '../components/icons/FarmIcons';
import { CROP_ICON } from '../components/icons/cropIcon';
import type { Zone, ZoneLiveState } from '@algaroshy/contracts';
import { apiFetch } from '../lib/api';
import { fmtNum, pickName, useT, type MsgKey } from '../lib/i18n';
import { useFarmConnector } from '../hooks/useFarmConnector';
import { SEVERITY, topSeverity } from '../lib/alarms';
import ZoneDrawer from '../components/ZoneDrawer';

type Filter = 'all' | 'running' | 'attention';

const STATE_COLOR: Record<string, string> = {
  running: '#00e5ff',
  faulted: '#ff5449',
  completed: '#7ee787',
  off: '#849396',
};

function stateColor(s?: string) {
  if (!s) return '#849396';
  return STATE_COLOR[s] ?? '#ffeb3b'; // transitional states
}

function hhmm(sec?: number) {
  const s = Math.round(sec ?? 0);
  return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}`;
}

export default function ZonesPage() {
  const { t, lang } = useT();
  const { state, sendCommand } = useFarmConnector();
  const { data, status, reload } = useLoad(() => apiFetch<Zone[]>('/api/v1/zones'));
  const config = data ?? [];
  const [filter, setFilter] = useState<Filter>('all');
  const [selected, setSelected] = useState<string | null>(null);

  const live = useMemo(
    () => Object.fromEntries((state?.zones ?? []).map((z) => [z.zone_id, z])) as Record<string, ZoneLiveState>,
    [state?.zones],
  );
  const alarmsByZone = useMemo(() => {
    const m: Record<string, NonNullable<typeof state>['active_alarms']> = {};
    for (const a of state?.active_alarms ?? []) if (a.zone_id) (m[a.zone_id] ??= []).push(a);
    return m;
  }, [state?.active_alarms]);

  const rows = config.filter((z) => {
    const l = live[z.id];
    if (filter === 'running') return l && l.state !== 'off' && l.state !== 'completed' && l.state !== 'faulted';
    if (filter === 'attention') return l?.state === 'faulted' || (alarmsByZone[z.id]?.length ?? 0) > 0 || (l?.moisture_pct ?? 50) < 25;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ZonesIcon size={24} className="text-[#00e5ff]" /> {t('zones.title')}
          </h1>
          <p className="text-sm text-[#849396] mt-1">{t('zones.subtitle')}</p>
        </div>
        <div className="flex gap-2 text-sm">
          {(['all', 'running', 'attention'] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg border ${filter === f ? 'bg-[#353534] border-[#849396]' : 'border-[#353534] text-[#849396] hover:bg-[#1c1b1b]'}`}
            >
              {t(`zones.filter.${f}` as MsgKey)}
            </button>
          ))}
        </div>
      </div>

      {status === 'loading' && <LoadingState />}
      {status === 'error' && <ErrorState onRetry={reload} />}
      {status === 'ok' && rows.length === 0 && <EmptyState art="zones" text={t('empty.zones')} />}

      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {rows.map((z) => {
          const l = live[z.id];
          const zoneAlarms = alarmsByZone[z.id] ?? [];
          const worst = topSeverity(zoneAlarms);
          const color = stateColor(l?.state);
          const moisture = l?.moisture_pct;
          return (
            <button
              key={z.id}
              onClick={() => setSelected(z.id)}
              className="panel text-start hover:border-white/25 p-4 space-y-3 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <CropBadge crop={z.crop_type} color={color} />
                <div className="min-w-0 flex-1">
                  <div className="font-bold text-lg truncate">{pickName(lang, z.name, z.name_ar)}</div>
                  <div className="text-xs text-[#849396]">
                    {t(`crop.${z.crop_type}` as MsgKey)} · <span dir="ltr">{fmtNum(z.area_ha, 2)} ha</span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-md text-xs font-bold border shrink-0" style={{ color, borderColor: `${color}66`, background: `${color}14` }}>
                  {t(`state.${l?.state ?? 'unknown'}` as MsgKey)}
                </span>
              </div>

              <div>
                <div className="flex justify-between text-xs text-[#849396] mb-1">
                  <span>{t('zones.moisture')}</span>
                  <span dir="ltr" className="font-mono text-[#e5e2e1]">{fmtNum(moisture, 1)}%</span>
                </div>
                <div className="h-1.5 bg-[#353534] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(100, moisture ?? 0)}%`,
                      background: (moisture ?? 0) < 25 ? '#ffeb3b' : (moisture ?? 0) > 80 ? '#4fc3f7' : '#7ee787',
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <Metric label={t('zones.flow')} value={`${fmtNum(l?.flow_m3h, 1)}`} unit="m³/h" />
                <Metric label={t('zones.pressure')} value={`${fmtNum(l?.pressure_bar, 2)}`} unit="bar" />
                <Metric label={t('zones.runtime')} value={hhmm(l?.runtime_sec)} />
              </div>

              <div className="flex items-center justify-between text-xs text-[#849396]">
                <span>
                  {t('zones.source')}: {l?.source_mode ? t(`source.${l.source_mode}` as MsgKey) : '—'}
                </span>
                {zoneAlarms.length > 0 && worst && (
                  <span className="font-bold" style={{ color: SEVERITY[worst].color }}>
                    {zoneAlarms.length} {t('zones.alarms')}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <ZoneDrawer zoneId={selected} zoneState={selected ? live[selected] : undefined} onClose={() => setSelected(null)} onCommand={sendCommand} />
    </div>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="bg-[#0e0e0e] border border-[#353534] rounded-lg px-2 py-1.5">
      <div className="text-[#849396] truncate">{label}</div>
      <div className="font-mono font-bold text-sm" dir="ltr">
        {value} {unit && <span className="text-[10px] text-[#849396]">{unit}</span>}
      </div>
    </div>
  );
}

function CropBadge({ crop, color }: { crop: string; color: string }) {
  const Icon = CROP_ICON[crop as keyof typeof CROP_ICON] ?? CROP_ICON.pomegranate;
  return (
    <span className="p-1.5 rounded-lg bg-white/5 shrink-0" style={{ color }}>
      <Icon size={24} />
    </span>
  );
}
