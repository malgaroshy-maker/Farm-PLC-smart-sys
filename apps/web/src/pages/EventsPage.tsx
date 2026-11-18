import { useEffect, useState } from 'react';
import EmptyState from '../components/EmptyState';
import { EventsIcon } from '../components/icons/FarmIcons';
import { apiFetch } from '../lib/api';
import { useT, type MsgKey } from '../lib/i18n';
import { useFarmStore } from '../store/farm';

interface EventRow {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  actor_type: string;
  actor_id: string | null;
  actor_name: string | null;
  payload: Record<string, unknown> | null;
  occurred_at: string;
}

type Cat = 'all' | 'command' | 'alarm' | 'user';
const PAGE = 50;

const TYPE_COLOR: Record<string, string> = {
  'command.rejected': '#ffb4ab',
  'command.failed': '#ffb4ab',
  'command.timed_out': '#ffb4ab',
  'command.completed': '#7ee787',
  'alarm.active': '#ff9f43',
  'alarm.reset': '#00e5ff',
  'alarm.acknowledged': '#ffeb3b',
  'zone.maintenance_done': '#ff9f43',
};

function fetchPage(cat: Cat, before?: number): Promise<EventRow[]> {
  const q = new URLSearchParams({ limit: String(PAGE) });
  if (cat !== 'all') q.set('category', cat);
  if (before) q.set('before_id', String(before));
  return apiFetch<EventRow[]>(`/api/v1/events?${q}`).catch(() => [] as EventRow[]);
}

function summarize(p: Record<string, unknown> | null): string {
  if (!p) return '';
  return Object.entries(p)
    .filter(([k, v]) => v != null && k !== 'command_id')
    .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    .join(' · ');
}

export default function EventsPage() {
  const { t, lang } = useT();
  const [cat, setCat] = useState<Cat>('all');
  const [rows, setRows] = useState<EventRow[]>([]);
  const [done, setDone] = useState(false);
  // refresh when commands/alarms change (cheap signal from the live store)
  const pulse = useFarmStore((s) => Object.keys(s.commands).length + (s.state?.active_alarms.length ?? 0));

  useEffect(() => {
    let live = true;
    fetchPage(cat).then((page) => {
      if (!live) return;
      setRows(page);
      setDone(page.length < PAGE);
    });
    return () => {
      live = false;
    };
  }, [cat, pulse]);

  const loadMore = async () => {
    const page = await fetchPage(cat, rows[rows.length - 1]?.id);
    setRows((prev) => [...prev, ...page]);
    setDone(page.length < PAGE);
  };

  const fmt = new Intl.DateTimeFormat(lang === 'ar' ? 'ar-LY-u-nu-latn' : 'en-GB', {
    timeZone: 'Africa/Tripoli',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <EventsIcon size={24} className="text-[#00e5ff]" /> {t('ev.title')}
          </h1>
          <p className="text-sm text-[#849396] mt-1">{t('ev.subtitle')}</p>
        </div>
        <div className="flex gap-2 text-sm">
          {(['all', 'command', 'alarm', 'user'] as Cat[]).map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`px-3 py-1.5 rounded-lg border ${cat === c ? 'bg-[#353534] border-[#849396]' : 'border-[#353534] text-[#849396] hover:bg-[#1c1b1b]'}`}
            >
              {t(`ev.cat.${c}` as MsgKey)}
            </button>
          ))}
        </div>
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="text-xs text-[#849396] bg-[#0e0e0e]">
            <tr>
              <th className="text-start p-3 w-40">{t('ev.when')}</th>
              <th className="text-start p-3">{t('ev.event')}</th>
              <th className="text-start p-3">{t('ev.target')}</th>
              <th className="text-start p-3">{t('ev.actor')}</th>
              <th className="text-start p-3">{t('ev.details')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-t border-[#353534] align-top">
                <td className="p-3 font-mono text-xs text-[#849396] whitespace-nowrap" dir="ltr">
                  {fmt.format(new Date(e.occurred_at))}
                </td>
                <td className="p-3 font-mono text-xs whitespace-nowrap" dir="ltr" style={{ color: TYPE_COLOR[e.event_type] ?? '#e5e2e1' }}>
                  {e.event_type}
                </td>
                <td className="p-3 font-mono text-xs" dir="ltr">
                  {e.entity_id ?? e.entity_type}
                </td>
                <td className="p-3 text-xs">{e.actor_name ?? t(`actor.${e.actor_type}` as MsgKey) ?? e.actor_type}</td>
                <td className="p-3 text-xs text-[#bac9cc] break-all" dir="ltr">
                  {summarize(e.payload)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5}>
                  <EmptyState art="events" text={t('empty.events')} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!done && rows.length > 0 && (
        <button onClick={loadMore} className="w-full py-2 rounded-lg border border-[#353534] text-[#bac9cc] hover:bg-[#1c1b1b]">
          {t('ev.more')}
        </button>
      )}
    </div>
  );
}
