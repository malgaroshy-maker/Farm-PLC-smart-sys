import { Pause, FastForward, Clock } from 'lucide-react';
import { useClockStore } from '../../lib/clock';
import { useT } from '../../lib/i18n';

interface Props {
  className?: string;
  compact?: boolean;
}

export default function SimTimeBadge({ className = '', compact = false }: Props) {
  const { t } = useT();
  const isSimulated = useClockStore((s) => s.isSimulated);
  const speed = useClockStore((s) => s.speed);
  const paused = useClockStore((s) => s.paused);

  if (!isSimulated) return null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border border-[#ff9f43]/40 bg-[#ff9f43]/15 text-[#ff9f43] shadow-[0_0_12px_rgba(255,159,67,0.2)] whitespace-nowrap transition-all ${className}`}
      title={paused ? t('clock.paused') : `${speed}× ${t('clock.simulated')}`}
    >
      {paused ? (
        <Pause size={12} className="shrink-0" />
      ) : speed > 1 ? (
        <FastForward size={12} className="shrink-0" />
      ) : (
        <Clock size={12} className="shrink-0" />
      )}
      <span>
        {paused ? (
          t('clock.paused')
        ) : (
          <>
            <span dir="ltr">{speed}×</span>
            {!compact && <span className="ms-1 font-sans">· {t('clock.simulated')}</span>}
          </>
        )}
      </span>
    </span>
  );
}
