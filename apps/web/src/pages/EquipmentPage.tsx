import { useEffect, useMemo, useState } from 'react';
import { EquipmentIcon, PumpIcon, SensorIcon, ValveIcon } from '../components/icons/FarmIcons';
import type { Pump, Sensor, Valve } from '@algaroshy/contracts';
import { apiFetch } from '../lib/api';
import { fmtNum, pickName, useT, type MsgKey } from '../lib/i18n';
import { useFarmStore } from '../store/farm';
import { ZONE_SEEDS } from '@algaroshy/contracts';

const STATUS_COLOR: Record<string, string> = {
  running: '#00e5ff',
  open: '#00e5ff',
  starting: '#ffeb3b',
  opening: '#ffeb3b',
  closing: '#ffeb3b',
  failed_start: '#ff5449',
  faulted: '#ff5449',
  fault: '#ff5449',
  bad: '#ff5449',
  stale: '#ffeb3b',
  good: '#7ee787',
};

function Badge({ text, status }: { text: string; status: string }) {
  const c = STATUS_COLOR[status] ?? '#849396';
  return (
    <span className="px-2 py-0.5 rounded-md text-xs font-bold border" style={{ color: c, borderColor: `${c}66`, background: `${c}14` }}>
      {text}
    </span>
  );
}

const zoneName = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));

export default function EquipmentPage() {
  const { t, lang } = useT();
  const state = useFarmStore((s) => s.state);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [valves, setValves] = useState<Valve[]>([]);
  const [sensors, setSensors] = useState<Sensor[]>([]);

  useEffect(() => {
    apiFetch<Pump[]>('/api/v1/pumps').then(setPumps).catch(() => null);
    apiFetch<Valve[]>('/api/v1/valves').then(setValves).catch(() => null);
    apiFetch<Sensor[]>('/api/v1/sensors').then(setSensors).catch(() => null);
  }, []);

  const livePumps = useMemo(() => Object.fromEntries((state?.pumps ?? []).map((p) => [p.pump_id, p])), [state?.pumps]);
  const liveValves = useMemo(() => Object.fromEntries((state?.valves ?? []).map((v) => [v.valve_id, v])), [state?.valves]);
  const liveSensors = useMemo(() => Object.fromEntries((state?.sensors ?? []).map((s) => [s.sensor_id, s])), [state?.sensors]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <EquipmentIcon size={24} className="text-[#00e5ff]" /> {t('eq.title')}
      </h1>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-[#bac9cc] flex items-center gap-2">
          <PumpIcon size={18} /> {t('eq.pumps')}
        </h2>
        <div className="grid md:grid-cols-2 gap-3">
          {pumps.map((p) => {
            const l = livePumps[p.id];
            const hours = l?.runtime_hours ?? p.runtime_hours;
            const due = p.service_interval_hours - (hours % p.service_interval_hours);
            const status = l?.state ?? 'stopped';
            return (
              <div key={p.id} className="panel overflow-hidden flex">
                <img src="/art/detail_pump.webp" alt="" className="w-28 sm:w-36 object-cover shrink-0" style={{ objectPosition: p.pump_type === 'well' ? '25% 50%' : '75% 50%' }} />
                <div className="flex-1 min-w-0 space-y-2 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-bold truncate">{pickName(lang, p.name, p.name_ar)}</div>
                    <Badge text={t(`pump.${status}` as MsgKey)} status={status} />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <Stat label={t('eq.runtime')} value={fmtNum(hours, 1)} unit={t('eq.hours')} />
                    <Stat label={t('eq.service')} value={fmtNum(due)} unit={t('eq.hours')} />
                    <Stat label={t('eq.startsToday')} value={fmtNum(l?.starts_today ?? 0)} />
                  </div>
                  <div className="text-xs text-[#849396]">
                    {t('eq.feedback')}: <span className={l?.run_fb ? 'text-[#00e5ff]' : ''}>{l?.run_fb ? 'ON' : 'OFF'}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-[#bac9cc] flex items-center gap-2">
          <ValveIcon size={18} /> {t('eq.valves')}
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {valves.map((v) => {
            const status = liveValves[v.id]?.status ?? 'unknown';
            const z = zoneName[v.zone_id];
            return (
              <div key={v.id} className="panel !rounded-lg px-3 py-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-bold truncate">{z ? pickName(lang, z.name, z.name_ar) : v.zone_id}</div>
                  <div className="text-[11px] text-[#849396] font-mono truncate" dir="ltr">{v.code}</div>
                </div>
                <Badge text={t(`valve.${status}` as MsgKey)} status={status} />
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-[#bac9cc] flex items-center gap-2">
          <SensorIcon size={18} /> {t('eq.sensors')}
        </h2>
        <div className="panel overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-[#849396] bg-[#0e0e0e]">
              <tr>
                <th className="text-start p-3">ID</th>
                <th className="text-start p-3">{t('eq.value')}</th>
                <th className="text-start p-3">{t('eq.quality')}</th>
              </tr>
            </thead>
            <tbody>
              {sensors.map((s) => {
                const l = liveSensors[s.id];
                const z = s.zone_id ? zoneName[s.zone_id] : null;
                const quality = l?.quality ?? 'stale';
                return (
                  <tr key={s.id} className="border-t border-[#353534]">
                    <td className="p-3">
                      <div className="font-bold">{z ? pickName(lang, z.name, z.name_ar) : s.code}</div>
                      <div className="text-[11px] text-[#849396] font-mono" dir="ltr">{s.code}</div>
                    </td>
                    <td className="p-3 font-mono" dir="ltr">
                      {fmtNum(l?.value, s.unit === 'bar' ? 2 : 1)} {s.unit}
                    </td>
                    <td className="p-3">
                      <Badge text={t(`quality.${quality}` as MsgKey)} status={quality} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="bg-[#0e0e0e] border border-[#353534] rounded-lg px-2 py-1.5 min-w-0">
      <div className="text-[#849396] truncate">{label}</div>
      <div className="font-mono font-bold text-sm">
        {value} {unit && <span className="text-[10px] text-[#849396]">{unit}</span>}
      </div>
    </div>
  );
}
