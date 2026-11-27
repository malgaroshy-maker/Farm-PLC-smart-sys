/**
 * Soil moisture (Milestone G7): start/stop levels per crop and the soil probes.
 * Owner's choice: the levels are shown first and confirmed by the owner; soil logic only acts on
 * confirmed levels. Values are % of available water (0 = tree can't drink, 100 = soil full).
 */
import { useState } from 'react';
import type { Zone } from '@algaroshy/contracts';
import { apiFetch, ApiError } from '../../lib/api';
import { pickName, useT, type MsgKey } from '../../lib/i18n';
import { refreshPoll, usePoll } from '../../lib/poll';
import { zoneList } from '../../lib/zones';

interface Level {
  crop_type: Zone['crop_type'];
  start_pct: number;
  stop_pct: number;
  confirmed: boolean;
}
interface Probe {
  id: string;
  external_id: string;
  zone_id: string;
  depth_cm: number;
  enabled: boolean;
}

const LEVELS = '/api/v1/soil/levels';
const PROBES = '/api/v1/soil/probes';
const field = 'bg-black/30 border border-white/10 rounded-lg px-2 py-1.5 text-xs w-full';

function errText(e: unknown, fallback: string) {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (typeof d === 'string') return d;
  }
  return fallback;
}

function LevelRow({ row }: { row: Level }) {
  const { t } = useT();
  const [v, setV] = useState(row);
  const [msg, setMsg] = useState<string | null>(null);
  const save = async (confirmed: boolean) => {
    setMsg(null);
    try {
      await apiFetch(`${LEVELS}/${row.crop_type}`, {
        method: 'PUT',
        body: JSON.stringify({ start_pct: v.start_pct, stop_pct: v.stop_pct, confirmed }),
      });
      setV({ ...v, confirmed });
      refreshPoll(LEVELS);
      setMsg(t('settings.saved'));
    } catch (e) {
      setMsg(errText(e, t('settings.saveFailed')));
    }
  };
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_5rem_5rem] sm:grid-cols-[minmax(0,1fr)_6rem_6rem_auto] gap-2 items-end p-3">
      <div className="text-sm font-bold">
        {t(`crop.${row.crop_type}` as MsgKey)}
        <div className={`text-[11px] font-normal ${v.confirmed ? 'text-[#7ee787]' : 'text-[#ff9f43]'}`}>
          {t(v.confirmed ? 'soil.confirmed' : 'soil.proposed')}
        </div>
      </div>
      <label className="text-[11px] text-[#849396]">
        {t('soil.start')}
        <input aria-label={`${t('soil.start')} ${t(`crop.${row.crop_type}` as MsgKey)}`} className={field} type="number" min={0} max={100} dir="ltr"
          value={v.start_pct} onChange={(e) => setV({ ...v, start_pct: (e.target.value === '' ? '' : Number(e.target.value)) as number })} />
      </label>
      <label className="text-[11px] text-[#849396]">
        {t('soil.stop')}
        <input aria-label={`${t('soil.stop')} ${t(`crop.${row.crop_type}` as MsgKey)}`} className={field} type="number" min={0} max={100} dir="ltr"
          value={v.stop_pct} onChange={(e) => setV({ ...v, stop_pct: (e.target.value === '' ? '' : Number(e.target.value)) as number })} />
      </label>
      <div className="col-span-3 sm:col-span-1 flex flex-wrap gap-2 items-center">
        <button type="button" onClick={() => save(true)} className="px-3 py-1.5 rounded-lg bg-[#00e5ff] text-[#0e0e0e] text-xs font-bold">
          {t('soil.confirm')}
        </button>
        {v.confirmed && (
          <button type="button" onClick={() => save(false)} className="px-3 py-1.5 rounded-lg border border-white/10 text-xs">
            {t('soil.unconfirm')}
          </button>
        )}
        {msg && <span className="text-[11px] text-[#bac9cc]" dir="auto">{msg}</span>}
      </div>
    </div>
  );
}

function Probes() {
  const { t, lang } = useT();
  const probes = usePoll<Probe[]>(PROBES, 60_000) ?? [];
  const zones = zoneList({ enabledOnly: true });
  const [form, setForm] = useState({ external_id: '', zone_id: zones[0]?.id ?? '', depth_cm: 30 });
  const [msg, setMsg] = useState<string | null>(null);
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      await apiFetch(PROBES, { method: 'POST', body: JSON.stringify(form) });
      setForm({ ...form, external_id: '' });
      refreshPoll(PROBES);
    } catch (ex) {
      setMsg(errText(ex, t('settings.saveFailed')));
    }
  };
  const disable = async (id: string) => {
    setMsg(null);
    await apiFetch(`${PROBES}/${id}`, { method: 'DELETE' }).catch((ex) => setMsg(errText(ex, t('settings.saveFailed'))));
    refreshPoll(PROBES);
  };
  const zoneName = (id: string) => {
    const z = zones.find((x) => x.id === id);
    return z ? pickName(lang, z.name, z.name_ar) : id;
  };
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-bold">{t('soil.probes')}</h3>
      <p className="text-[11px] text-[#849396]">{t('soil.probesHelp')}</p>
      {probes.length > 0 && (
        <div className="panel divide-y divide-white/5">
          {probes.map((p) => (
            <div key={p.id} className={`flex items-center gap-3 p-3 text-sm ${p.enabled ? '' : 'opacity-50'}`}>
              <bdi dir="ltr" className="font-mono text-xs">{p.external_id}</bdi>
              <span className="flex-1">{zoneName(p.zone_id)} · <bdi dir="ltr">{p.depth_cm} cm</bdi></span>
              {p.enabled && (
                <button type="button" onClick={() => disable(p.id)} className="px-2.5 py-1 rounded-lg border border-white/10 text-xs">
                  {t('soil.disableProbe')}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      <form onSubmit={add} className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 rounded-xl border border-white/10">
        <label className="text-[11px] text-[#849396] col-span-2 sm:col-span-1">
          {t('soil.probeId')}
          <input className={field} dir="ltr" required minLength={3} value={form.external_id} placeholder="A840414BC1D2E3F4"
            onChange={(e) => setForm({ ...form, external_id: e.target.value })} />
        </label>
        <label className="text-[11px] text-[#849396]">
          {t('soil.zone')}
          <select className={field} value={form.zone_id} onChange={(e) => setForm({ ...form, zone_id: e.target.value })}>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>{pickName(lang, z.name, z.name_ar)}</option>
            ))}
          </select>
        </label>
        <label className="text-[11px] text-[#849396]">
          {t('soil.depth')}
          <input className={field} type="number" min={5} max={200} dir="ltr" value={form.depth_cm}
            onChange={(e) => setForm({ ...form, depth_cm: Number(e.target.value) })} />
        </label>
        <div className="flex items-end gap-2">
          <button type="submit" className="px-3 py-1.5 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-xs font-bold">{t('soil.addProbe')}</button>
        </div>
        {msg && <p className="col-span-2 sm:col-span-4 text-xs text-[#ff5449]" dir="auto">{msg}</p>}
      </form>
    </div>
  );
}

export default function SoilSection() {
  const { t } = useT();
  const levels = usePoll<Level[]>(LEVELS, 120_000);
  return (
    <section className="space-y-3" data-testid="soil-section">
      <h2 className="text-base font-bold">{t('soil.title')}</h2>
      <p className="text-xs text-[#bac9cc]">{t('soil.explain')}</p>
      <div className="panel divide-y divide-white/5">
        {(levels ?? []).map((row) => (
          <LevelRow key={`${row.crop_type}-${row.confirmed}`} row={row} />
        ))}
      </div>
      <Probes />
    </section>
  );
}
