/** Zones & equipment (owner: edit + add + disable; never delete — history stays). */
import { useState } from 'react';
import type { Zone } from '@algaroshy/contracts';
import { ApiError } from '../../lib/api';
import { pickName, useT, type MsgKey } from '../../lib/i18n';
import { createZone, updateZone, type NewZone } from '../../lib/settingsApi';
import { useZoneCatalog, zoneList } from '../../lib/zones';
import { Switch } from './FeaturesTab';

const CROPS: Zone['crop_type'][] = ['pomegranate', 'olives', 'grapes', 'mixed_fruit', 'other'];
type Editable = Pick<Zone, 'name' | 'name_ar' | 'crop_type' | 'area_ha' | 'max_runtime_min' | 'default_duration_min' | 'flow_min_m3h' | 'flow_max_m3h'>;
const NUM_FIELDS: (keyof Editable)[] = ['area_ha', 'max_runtime_min', 'default_duration_min', 'flow_min_m3h', 'flow_max_m3h'];

function errText(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (typeof d === 'string') return d;
  }
  return fallback;
}

function ZoneForm({ initial, onSave, onCancel, isNew }: { initial: Editable & { code?: string }; onSave: (v: Editable & { code?: string }) => Promise<void>; onCancel: () => void; isNew?: boolean }) {
  const { t } = useT();
  const [v, setV] = useState(initial);
  const [err, setErr] = useState<string | null>(null);
  const field = 'bg-black/30 border border-white/10 rounded-lg px-2 py-1.5 text-xs w-full';
  const set = <K extends keyof typeof v>(k: K, val: (typeof v)[K]) => setV({ ...v, [k]: val });
  return (
    <form
      className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 rounded-xl border border-[#00e5ff]/30"
      onSubmit={async (e) => {
        e.preventDefault();
        setErr(null);
        try {
          await onSave(v);
        } catch (ex) {
          setErr(errText(ex, t('settings.saveFailed')));
        }
      }}
    >
      {isNew && (
        <label className="text-[11px] text-[#849396] col-span-2 sm:col-span-1">
          {t('zoneAdmin.code')}
          <input className={field} dir="ltr" value={v.code ?? ''} onChange={(e) => set('code', e.target.value.toUpperCase())} placeholder="LEMON_1" required />
        </label>
      )}
      <label className="text-[11px] text-[#849396]">
        {t('zoneAdmin.nameAr')}
        <input className={field} value={v.name_ar} onChange={(e) => set('name_ar', e.target.value)} required />
      </label>
      <label className="text-[11px] text-[#849396]">
        {t('zoneAdmin.nameEn')}
        <input className={field} dir="ltr" value={v.name} onChange={(e) => set('name', e.target.value)} required />
      </label>
      <label className="text-[11px] text-[#849396]">
        {t('zoneAdmin.crop')}
        <select className={field} value={v.crop_type} onChange={(e) => set('crop_type', e.target.value as Zone['crop_type'])}>
          {CROPS.map((c) => (
            <option key={c} value={c}>
              {t(`crop.${c}` as MsgKey)}
            </option>
          ))}
        </select>
      </label>
      {NUM_FIELDS.map((k) => (
        <label key={k} className="text-[11px] text-[#849396]">
          {t(`zoneAdmin.${k}` as MsgKey)}
          <input className={field} type="number" step="any" min={0} dir="ltr" value={v[k] as number} onChange={(e) => set(k, Number(e.target.value) as never)} required />
        </label>
      ))}
      <div className="col-span-2 sm:col-span-4 flex items-center gap-2">
        <button type="submit" className="px-3 py-1.5 rounded-lg bg-[#00e5ff] text-[#0e0e0e] text-xs font-bold">
          {t('settings.save')}
        </button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 rounded-lg border border-white/10 text-xs">
          {t('common.cancel')}
        </button>
        {err && <span className="text-xs text-[#ff5449]" dir="auto">{err}</span>}
      </div>
    </form>
  );
}

export default function ZonesTab() {
  const { t, lang } = useT();
  useZoneCatalog((s) => s.version); // re-render when names change
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const zones = zoneList();

  return (
    <div className="space-y-3" data-testid="zones-tab">
      <p className="text-xs text-[#bac9cc]">{t('zoneAdmin.intro')}</p>
      <div className="panel divide-y divide-white/5">
        {zones.map((z) => (
          <div key={z.id} className="p-3 space-y-2">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className={`text-sm font-bold ${z.enabled === false ? 'text-[#849396] line-through' : ''}`}>{pickName(lang, z.name, z.name_ar)}</div>
                <div className="text-[11px] text-[#849396]">
                  {t(`crop.${z.crop_type}` as MsgKey)} · <bdi className="font-mono">{z.area_ha} ha · ≤ {z.max_runtime_min} {t('common.min')} · {z.flow_min_m3h}–{z.flow_max_m3h} m³/h</bdi>
                </div>
              </div>
              <button onClick={() => setEditing(editing === z.id ? null : z.id)} className="px-2.5 py-1 rounded-lg border border-white/10 text-xs">
                {t('zoneAdmin.edit')}
              </button>
              <Switch on={z.enabled !== false} onChange={(v) => void updateZone(z.id, { enabled: v })} label={t('zoneAdmin.enabled')} />
            </div>
            {editing === z.id && (
              <ZoneForm
                initial={z}
                onCancel={() => setEditing(null)}
                onSave={async (v) => {
                  await updateZone(z.id, v);
                  setEditing(null);
                }}
              />
            )}
          </div>
        ))}
      </div>
      {adding ? (
        <ZoneForm
          isNew
          initial={{ code: '', name: '', name_ar: '', crop_type: 'other', area_ha: 0.5, max_runtime_min: 90, default_duration_min: 45, flow_min_m3h: 2, flow_max_m3h: 8 }}
          onCancel={() => setAdding(false)}
          onSave={async (v) => {
            await createZone(v as NewZone);
            setAdding(false);
          }}
        />
      ) : (
        <button onClick={() => setAdding(true)} className="px-3 py-1.5 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-xs font-bold" data-testid="zone-add">
          {t('zoneAdmin.add')}
        </button>
      )}
      <p className="text-[11px] text-[#849396]">{t('zoneAdmin.mapNote')}</p>
    </div>
  );
}
