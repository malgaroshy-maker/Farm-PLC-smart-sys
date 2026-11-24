/** G7: a zone's soil moisture against its start/stop levels (% of available water). */
import { usePoll } from '../lib/poll';
import { fmtNum, useT, type MsgKey } from '../lib/i18n';

interface SoilStatus {
  zone_id: string;
  moisture_pct: number | null;
  source: 'probe' | 'controller' | 'none';
  start_pct: number;
  stop_pct: number;
  confirmed: boolean;
  state: 'dry' | 'ok' | 'full' | 'unknown';
}

const COLOR = { dry: '#ff9f43', ok: '#7ee787', full: '#00e5ff', unknown: '#849396' } as const;

export default function SoilLine({ zoneId }: { zoneId: string }) {
  const { t } = useT();
  const all = usePoll<SoilStatus[]>('/api/v1/soil/status', 60_000);
  const s = all?.find((x) => x.zone_id === zoneId);
  if (!s) return null;
  const pct = (v: number) => `${Math.max(0, Math.min(100, v))}%`;
  const color = COLOR[s.state];
  return (
    <section className="panel p-4 space-y-2" aria-label={t('soil.title')}>
      <div className="flex items-center justify-between text-sm">
        <span className="font-bold">{t('soil.band')}</span>
        <span className="font-bold" style={{ color }}>
          {s.moisture_pct != null && <bdi dir="ltr" className="font-mono me-2">{fmtNum(s.moisture_pct, 0)}%</bdi>}
          {t(`soil.state.${s.state}` as MsgKey)}
        </span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/10" dir="ltr">
        <div className="absolute inset-y-0 rounded-full bg-[#7ee787]/25" style={{ left: pct(s.start_pct), right: `calc(100% - ${pct(s.stop_pct)})` }} />
        {s.moisture_pct != null && (
          <div className="absolute -top-1 w-1.5 h-4.5 rounded-full" style={{ left: `calc(${pct(s.moisture_pct)} - 3px)`, background: color }} />
        )}
      </div>
      <div className="flex justify-between text-[11px] text-[#849396]">
        <span>
          {t('soil.start')} <bdi dir="ltr">{fmtNum(s.start_pct, 0)}</bdi> · {t('soil.stop')} <bdi dir="ltr">{fmtNum(s.stop_pct, 0)}</bdi>
        </span>
        {!s.confirmed && <span className="text-[#ff9f43]">{t('soil.notConfirmed')}</span>}
      </div>
    </section>
  );
}
