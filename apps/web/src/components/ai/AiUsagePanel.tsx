/**
 * AI usage (Milestone G2): how often each feature/model is used, how fast it answers,
 * how often it falls back, and estimated token use. Admin only (AI settings page).
 */
import { useEffect, useState } from 'react';
import { BarChart3 } from 'lucide-react';
import { fetchAiUsage, type AiUsage, type AiUsageRow } from '../../lib/api';
import { fmtNum, useT, type MsgKey } from '../../lib/i18n';

function secs(ms: number): string {
  return ms >= 1000 ? `${fmtNum(ms / 1000, 1)} s` : `${fmtNum(ms, 0)} ms`;
}

function Table({ rows, label }: { rows: AiUsageRow[]; label: MsgKey }) {
  const { t } = useT();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-white/10 text-[#849396] text-[11px]">
            <th className="py-2 px-2 text-start font-medium">{t(label)}</th>
            <th className="py-2 px-2 text-start font-medium">{t('aiUsage.calls')}</th>
            <th className="py-2 px-2 text-start font-medium">{t('aiUsage.avg')}</th>
            <th className="py-2 px-2 text-start font-medium">{t('aiUsage.p95')}</th>
            <th className="py-2 px-2 text-start font-medium">{t('aiUsage.fallbacks')}</th>
            <th className="py-2 px-2 text-start font-medium">{t('aiUsage.tokens')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((r) => (
            <tr key={r.name}>
              <td className="py-2 px-2 font-mono text-[11px] text-[#e5e2e1] whitespace-nowrap">{r.name}</td>
              <td className="py-2 px-2 font-mono">{r.calls}</td>
              <td className="py-2 px-2 font-mono text-[#00e5ff]">{secs(r.avg_ms)}</td>
              <td className="py-2 px-2 font-mono">{secs(r.p95_ms)}</td>
              <td className={`py-2 px-2 font-mono ${r.fallbacks ? 'text-[#ff9f43]' : ''}`}>{r.fallbacks}</td>
              <td className="py-2 px-2 font-mono">{fmtNum(r.input_tokens + r.output_tokens, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AiUsagePanel() {
  const { t } = useT();
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AiUsage | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let live = true;
    fetchAiUsage(days)
      .then((d) => live && (setData(d), setError(false)))
      .catch(() => live && setError(true));
    return () => {
      live = false;
    };
  }, [days]);

  const total = data?.total;
  const okPct = total && total.calls ? Math.round(((total.calls - total.rule_based) / total.calls) * 100) : null;

  return (
    <section className="panel p-5 space-y-4" data-testid="ai-usage">
      <div className="flex items-center justify-between border-b border-white/5 pb-3 gap-2">
        <div className="flex items-center gap-2">
          <BarChart3 className="text-[#00e5ff]" size={18} />
          <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiUsage.title')}</h2>
        </div>
        <div className="flex gap-1">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              aria-pressed={days === d}
              className={`px-2 py-0.5 rounded text-[11px] ${days === d ? 'bg-[#00e5ff]/15 text-[#00e5ff]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}
            >
              {t(`aiUsage.days.${d}` as MsgKey)}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="text-xs text-[#ff5449]">{t('aiUsage.error')}</div>}
      {data && total && total.calls === 0 && <div className="text-xs text-[#849396]">{t('aiUsage.empty')}</div>}

      {data && total && total.calls > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { k: 'aiUsage.calls', v: String(total.calls) },
              { k: 'aiUsage.aiAnswered', v: okPct == null ? '—' : `${okPct} %` },
              { k: 'aiUsage.avg', v: secs(total.avg_ms) },
              { k: 'aiUsage.tokens', v: fmtNum(total.input_tokens + total.output_tokens, 0) },
            ].map(({ k, v }) => (
              <div key={k} className="rounded-xl border border-white/[0.07] p-3">
                <div className="text-[11px] text-[#849396]">{t(k as MsgKey)}</div>
                <div className="text-lg font-bold font-mono text-[#e5e2e1]">{v}</div>
              </div>
            ))}
          </div>
          <Table rows={data.by_feature} label="aiUsage.feature" />
          <Table rows={data.by_model} label="aiUsage.model" />
          {Object.keys(data.fallback_reasons).length > 0 && (
            <div className="text-[11px] text-[#bac9cc] flex flex-wrap gap-2">
              <span className="text-[#849396]">{t('aiUsage.reasons')}</span>
              {Object.entries(data.fallback_reasons).map(([k, n]) => (
                <span key={k} className="px-2 py-0.5 rounded bg-[#ff9f43]/15 text-[#ff9f43] border border-[#ff9f43]/30 font-mono">
                  {k} × {n}
                </span>
              ))}
            </div>
          )}
          <p className="text-[11px] text-[#849396]">{t('aiUsage.note')}</p>
        </>
      )}
    </section>
  );
}
