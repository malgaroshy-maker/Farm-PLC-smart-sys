import { WifiOff } from 'lucide-react';
import { isOffline, useFarmStore } from '../store/farm';
import { useT } from '../lib/i18n';

/** Full-width warning whenever the screen no longer shows what is happening at the farm. */
export default function OfflineBanner() {
  const offline = useFarmStore(isOffline);
  const lastDataAt = useFarmStore((s) => s.lastDataAt);
  const { t, lang } = useT();
  if (!offline) return null;
  const at = lastDataAt
    ? new Date(lastDataAt).toLocaleTimeString(lang === 'ar' ? 'ar-LY-u-nu-latn' : 'en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      })
    : null;
  return (
    <div
      role="alert"
      data-testid="offline-banner"
      className="shrink-0 flex items-center justify-center gap-2 px-3 py-2 bg-[#93000a] text-[#ffdad6] text-sm font-bold text-center"
    >
      <WifiOff size={16} className="shrink-0" />
      <span>
        {t('offline.title')}
        {at && ` · ${t('offline.lastUpdate')} ${at}`}
        <span className="font-normal"> — {t('offline.hint')}</span>
      </span>
    </div>
  );
}
