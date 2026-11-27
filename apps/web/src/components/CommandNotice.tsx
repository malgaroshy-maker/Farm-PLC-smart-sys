/** What happened to a command after it was sent: the last word comes from the controller. */
import { useEffect, useState } from 'react';
import { COMMAND_DONE, useCommandResult } from '../lib/useCommandResult';
import { failureText } from '../lib/commandText';
import { useT } from '../lib/i18n';

export function StopAllNotice({ id, onClose }: { id: string; onClose: () => void }) {
  const { t } = useT();
  const cmd = useCommandResult(id);
  const [late, setLate] = useState(false);
  const status = cmd?.status ?? 'pending';
  const done = COMMAND_DONE.includes(status);

  useEffect(() => {
    const timer = setTimeout(() => setLate(true), 15000);
    return () => clearTimeout(timer);
  }, [id]);

  useEffect(() => {
    if (status !== 'completed') return;
    const timer = setTimeout(onClose, 5000);
    return () => clearTimeout(timer);
  }, [status, onClose]);

  const bad = (done && status !== 'completed') || (!done && late);
  const text =
    status === 'completed'
      ? t('stop.done')
      : done
        ? `${t('stop.failed')} — ${failureText(cmd?.failure_reason)}`
        : late
          ? t('stop.notConfirmed')
          : t('stop.sending');
  return (
    <div
      role={bad ? 'alert' : 'status'}
      data-testid="stop-all-notice"
      className={`shrink-0 flex items-center justify-center gap-3 px-3 py-2 text-sm font-bold text-center ${
        bad ? 'bg-[#93000a] text-[#ffdad6]' : 'bg-[#353534] text-[#e5e2e1]'
      }`}
    >
      <span>{text}</span>
      {(done || late) && (
        <button type="button" onClick={onClose} className="underline text-xs shrink-0">
          {t('common.dismiss')}
        </button>
      )}
    </div>
  );
}
