/**
 * System health panel (Milestone G1): opened from the Live badge. Shows every check from
 * /api/v1/system/health with what is wrong and what to do, in Arabic or English.
 */
import { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw, X } from 'lucide-react';
import { apiFetch, HEALTH_COLOR, SYSTEM_HEALTH_PATH, type SystemHealth } from '../lib/api';
import { fmtNum, useT, type MsgKey } from '../lib/i18n';

const ICON = { ok: CheckCircle2, warn: AlertTriangle, fail: XCircle };

function uptime(sec: number, lang: 'ar' | 'en'): string {
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return lang === 'ar' ? `${d} ي ${h} س ${m} د` : `${d}d ${h}h ${m}m`;
}

/** Small human-readable facts from a check's detail (numbers only; no internals). */
function facts(detail: Record<string, string | number | null>): string[] {
  const out: string[] = [];
  if (typeof detail.ms === 'number') out.push(`${fmtNum(detail.ms, 1)} ms`);
  if (typeof detail.age_sec === 'number') out.push(`${fmtNum(detail.age_sec, 0)} s`);
  if (typeof detail.free_gb === 'number') out.push(`${fmtNum(detail.free_gb, 1)} GB`);
  if (typeof detail.db_mb === 'number') out.push(`DB ${fmtNum(detail.db_mb, 1)} MB`);
  if (typeof detail.source === 'string') out.push(detail.source);
  return out;
}

export default function HealthPanel({ initial, onClose }: { initial: SystemHealth | null; onClose: () => void }) {
  const { t, lang } = useT();
  const [data, setData] = useState<SystemHealth | null>(initial);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    setBusy(true);
    try {
      setData(await apiFetch<SystemHealth>(SYSTEM_HEALTH_PATH));
      setError(false);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const first = setTimeout(() => void refresh(), 0); // fresh check when the panel opens
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(first);
      window.removeEventListener('keydown', onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const overall = data?.status ?? 'warn';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="health-title"
        className="panel w-full max-w-md max-h-[85vh] overflow-y-auto p-4 space-y-3 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        data-testid="health-panel"
      >
        <div className="flex items-center gap-2">
          <h2 id="health-title" className="text-base font-bold">
            {t('health.title')}
          </h2>
          <button onClick={refresh} disabled={busy} className="ms-auto p-1.5 rounded-lg text-[#849396] hover:text-[#e5e2e1]" aria-label={t('health.refresh')} title={t('health.refresh')}>
            <RefreshCw size={16} className={busy ? 'animate-spin' : undefined} />
          </button>
          <button onClick={onClose} className="p-1.5 rounded-lg text-[#849396] hover:text-[#e5e2e1]" aria-label="close">
            <X size={16} />
          </button>
        </div>

        {error && <div className="text-sm text-[#ff5449]">{t('health.unreachable')}</div>}
        {!data && !error && <div className="text-sm text-[#849396]">{t('health.loading')}</div>}

        {data && (
          <>
            <div className="text-sm font-bold" style={{ color: HEALTH_COLOR[overall] }}>
              {t(`health.overall.${overall}` as MsgKey)}
            </div>
            <ul className="space-y-2">
              {data.checks.map((c) => {
                const Icon = ICON[c.status];
                const f = facts(c.detail);
                return (
                  <li key={c.key} className="flex gap-3 rounded-xl border border-white/[0.07] p-3" data-testid={`health-${c.key}`}>
                    <Icon size={18} className="shrink-0 mt-0.5" style={{ color: HEALTH_COLOR[c.status] }} />
                    <div className="min-w-0 space-y-0.5">
                      <div className="text-sm font-bold">
                        {t(`health.check.${c.key}` as MsgKey)}{' '}
                        <span className="text-xs font-normal" style={{ color: HEALTH_COLOR[c.status] }}>
                          · {t(`health.status.${c.status}` as MsgKey)}
                        </span>
                      </div>
                      <div className="text-xs text-[#bac9cc]">{t(`health.code.${c.code}` as MsgKey)}</div>
                      {f.length > 0 && (
                        <div className="text-[11px] text-[#849396] font-mono" dir="ltr">
                          {f.join(' · ')}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="flex justify-between text-[11px] text-[#849396]">
              <span>
                {t('health.version')} <bdi className="font-mono">{data.version}</bdi>
              </span>
              <span>
                {t('health.uptime')} <bdi>{uptime(data.uptime_sec, lang)}</bdi>
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
