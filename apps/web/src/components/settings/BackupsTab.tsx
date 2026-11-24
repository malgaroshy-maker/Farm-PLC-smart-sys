/** G7: Settings → Backups. Daily copies, Back up now, and a restore applied on the next restart. */
import { useState } from 'react';
import { DatabaseBackup, HardDrive, Cloud, RotateCcw } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { refreshPoll, usePoll } from '../../lib/poll';
import { fmtNum, useT, type MsgKey } from '../../lib/i18n';

interface BackupFile {
  name: string;
  size_bytes: number;
  created_at: string;
}
interface LastBackup {
  name: string;
  at: string;
  reason: string;
  size_bytes: number;
  usb: string;
  drive: string;
}
interface BackupStatus {
  enabled: boolean;
  keep: number;
  time: string;
  usb_dir: string | null;
  usb_present: boolean;
  drive_remote: string | null;
  rclone_found: boolean;
  last: LastBackup | null;
  pending_restore: string | null;
  backups: BackupFile[];
}

const PATH = '/api/v1/backups';
const mb = (b: number) => `${fmtNum(b / (1024 * 1024), 1)} MB`;
const nameTime = (name: string) => `${name.slice(5, 9)}-${name.slice(9, 11)}-${name.slice(11, 13)} ${name.slice(14, 16)}:${name.slice(16, 18)}`;

/** ok | off | missing | rclone_missing | failed:* → one translated word + colour. */
function copyState(v: string | undefined): { key: MsgKey; color: string } {
  if (v === 'ok') return { key: 'backup.copy.ok', color: '#7ee787' };
  if (v === 'missing') return { key: 'backup.copy.missing', color: '#ff9f43' };
  if (v === 'rclone_missing') return { key: 'backup.copy.rcloneMissing', color: '#ff9f43' };
  if (v?.startsWith('failed')) return { key: 'backup.copy.failed', color: '#ffb4ab' };
  return { key: 'backup.copy.off', color: '#849396' };
}

export default function BackupsTab() {
  const { t } = useT();
  const s = usePoll<BackupStatus>(PATH, 60_000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refreshPoll(PATH);
    } catch {
      setError(t('settings.saveFailed'));
    } finally {
      setBusy(false);
    }
  };

  if (!s) return <div className="text-sm text-[#849396]">{t('common.loading')}</div>;
  if (!s.enabled) return <div className="panel p-4 text-sm text-[#bac9cc]">{t('backup.notSqlite')}</div>;

  const usb = copyState(s.last?.usb);
  const drive = copyState(s.last?.drive);
  const restore = (name: string) => {
    if (!window.confirm(t('backup.restoreConfirm').replace('{when}', nameTime(name)))) return;
    void act(() => apiFetch(`/api/v1/backups/${encodeURIComponent(name)}/restore`, { method: 'POST' }));
  };

  return (
    <div className="space-y-4" data-testid="backups-tab">
      {s.pending_restore && (
        <div className="panel p-3 border-[#ff9f43]/40 bg-[#ff9f43]/10 flex flex-wrap items-center justify-between gap-2" role="status">
          <span className="text-sm text-[#ffd8a8]">
            {t('backup.pending').replace('{when}', nameTime(s.pending_restore))}
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => apiFetch('/api/v1/backups/restore', { method: 'DELETE' }))}
            className="px-3 py-1 rounded-lg border border-white/15 text-xs font-bold hover:bg-white/5 disabled:opacity-50"
          >
            {t('backup.cancelRestore')}
          </button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <section className="panel p-4 space-y-2">
          <h2 className="text-sm font-bold flex items-center gap-1.5">
            <DatabaseBackup size={16} className="text-[#00e5ff]" />
            {t('backup.last')}
          </h2>
          {s.last ? (
            <div className="text-sm">
              <bdi dir="ltr" className="font-mono">{nameTime(s.last.name)}</bdi>
              <div className="text-[11px] text-[#849396]">
                {t(s.last.reason === 'daily' ? 'backup.reason.daily' : 'backup.reason.manual')} · <bdi dir="ltr">{mb(s.last.size_bytes)}</bdi>
              </div>
            </div>
          ) : (
            <div className="text-sm text-[#849396]">{t('backup.none')}</div>
          )}
          <div className="text-[11px] text-[#849396]">
            {t('backup.schedule').replace('{time}', s.time).replace('{keep}', String(s.keep))}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => apiFetch('/api/v1/backups', { method: 'POST' }))}
            className="mt-1 px-3 py-1.5 rounded-xl bg-[#00e5ff] text-[#0e0e0e] text-xs font-bold disabled:opacity-50"
            data-testid="backup-now"
          >
            {busy ? t('backup.working') : t('backup.now')}
          </button>
        </section>

        <section className="panel p-4 space-y-2">
          <h2 className="text-sm font-bold flex items-center gap-1.5">
            <HardDrive size={16} className="text-[#00e5ff]" />
            {t('backup.usb')}
          </h2>
          {s.usb_dir ? (
            <>
              <bdi dir="ltr" className="block font-mono text-xs break-all">{s.usb_dir}</bdi>
              <div className="text-xs" style={{ color: s.usb_present ? '#7ee787' : '#ff9f43' }}>
                {t(s.usb_present ? 'backup.usb.present' : 'backup.usb.absent')}
              </div>
              {s.last && <div className="text-[11px]" style={{ color: usb.color }}>{t('backup.lastCopy')}: {t(usb.key)}</div>}
            </>
          ) : (
            <div className="text-xs text-[#849396]">{t('backup.usb.notSet')}</div>
          )}
        </section>

        <section className="panel p-4 space-y-2">
          <h2 className="text-sm font-bold flex items-center gap-1.5">
            <Cloud size={16} className="text-[#00e5ff]" />
            {t('backup.drive')}
          </h2>
          {s.drive_remote ? (
            <>
              <bdi dir="ltr" className="block font-mono text-xs break-all">{s.drive_remote}</bdi>
              {!s.rclone_found && <div className="text-xs text-[#ff9f43]">{t('backup.copy.rcloneMissing')}</div>}
              {s.last && <div className="text-[11px]" style={{ color: drive.color }}>{t('backup.lastCopy')}: {t(drive.key)}</div>}
            </>
          ) : (
            <div className="text-xs text-[#849396]">{t('backup.drive.notSet')}</div>
          )}
        </section>
      </div>

      {error && <div className="text-xs text-[#ffb4ab]">{error}</div>}

      <section className="panel p-4 space-y-2">
        <h2 className="text-sm font-bold">{t('backup.list')}</h2>
        <p className="text-[11px] text-[#849396]">{t('backup.restoreHelp')}</p>
        {s.backups.length === 0 ? (
          <div className="text-sm text-[#849396]">{t('backup.none')}</div>
        ) : (
          <ul className="divide-y divide-white/5">
            {s.backups.map((b) => (
              <li key={b.name} className="flex items-center justify-between gap-2 py-2">
                <div className="min-w-0">
                  <bdi dir="ltr" className="font-mono text-sm">{nameTime(b.name)}</bdi>
                  <span className="text-[11px] text-[#849396] ms-2"><bdi dir="ltr">{mb(b.size_bytes)}</bdi></span>
                </div>
                <button
                  type="button"
                  disabled={busy || s.pending_restore === b.name}
                  onClick={() => restore(b.name)}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/10 text-xs hover:bg-white/5 disabled:opacity-40"
                >
                  <RotateCcw size={13} />
                  {t('backup.restore')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
