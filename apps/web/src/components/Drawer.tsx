import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { useT } from '../lib/i18n';

/** A side panel that closes with Escape or a click outside. */
export default function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const { t } = useT();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <>
      <div className="fixed inset-0 z-50 bg-black/60" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="fixed inset-y-0 end-0 z-50 w-full max-w-md bg-[#161618] border-s border-white/10 flex flex-col shadow-2xl"
      >
        <div className="p-4 border-b border-white/10 flex items-center justify-between gap-2">
          <h2 className="text-base font-bold text-[#e5e2e1]">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t('drawer.close')} className="p-2 min-w-11 min-h-11 flex items-center justify-center text-[#849396] hover:text-[#e5e2e1]">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </>
  );
}
