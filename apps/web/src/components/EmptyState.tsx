import { RotateCw } from 'lucide-react';
import { useT } from '../lib/i18n';

export type EmptyArt = 'alarms' | 'events' | 'schedules' | 'zones' | 'equipment';

/** Calm illustrated empty state (art approved in design/samples-r2; G4 adds one per page). */
export default function EmptyState({ art, text, children }: { art: EmptyArt; text: string; children?: React.ReactNode }) {
  return (
    <div role="status" className="flex flex-col items-center gap-4 py-10 px-4 text-center">
      <img src={`/art/empty_${art}.webp`} alt="" className="w-56 max-w-full rounded-2xl opacity-90 shadow-lg" loading="lazy" />
      <p className="text-sm text-[#bac9cc] max-w-xs">{text}</p>
      {children}
    </div>
  );
}

/** Load failure (G4): calm art, a plain reason and a Retry button, never a blank page or an endless spinner. */
export function ErrorState({ text, onRetry }: { text?: string; onRetry?: () => void }) {
  const { t } = useT();
  return (
    <div role="alert" className="flex flex-col items-center gap-4 py-10 px-4 text-center">
      <img src="/art/state_offline.webp" alt="" className="w-56 max-w-full rounded-2xl opacity-90 shadow-lg" loading="lazy" />
      <p className="text-sm text-[#bac9cc] max-w-xs">{text ?? t('state.loadError')}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1.5 px-4 py-2 min-h-11 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-sm font-bold"
        >
          <RotateCw size={16} aria-hidden="true" />
          {t('state.retry')}
        </button>
      )}
    </div>
  );
}

/** Loading placeholder with a live region so screen readers hear it. */
export function LoadingState() {
  const { t } = useT();
  return (
    <div role="status" aria-live="polite" className="panel p-8 text-center text-sm text-[#849396]">
      {t('common.loading')}
    </div>
  );
}
