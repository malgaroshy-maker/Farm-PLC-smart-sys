/**
 * "Maintenance done" sign-off for a zone. Faults before this moment stop
 * counting towards ALM-036 (repeated faults), so that alarm clears.
 */
import { useState } from 'react';
import { Wrench } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useT } from '../lib/i18n';

export default function MaintenanceDone({ zoneId }: { zoneId: string }) {
  const { can } = useAuth();
  const { t } = useT();
  const [step, setStep] = useState<'idle' | 'confirm' | 'busy' | 'done'>('idle');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  if (!can('owner_admin', 'operator')) return null;

  const submit = async () => {
    setStep('busy');
    setError(null);
    try {
      await apiFetch(`/api/v1/zones/${zoneId}/maintenance-done`, {
        method: 'POST',
        body: JSON.stringify(note.trim() ? { note: note.trim() } : {}),
      });
      setStep('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStep('confirm');
    }
  };

  if (step === 'done') return <p className="text-xs text-[#7ee787]">✓ {t('maint.saved')}</p>;
  if (step === 'idle')
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          setStep('confirm');
        }}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#ff9f43]/60 text-[#ff9f43] hover:bg-[#ff9f43]/10 text-xs font-bold"
      >
        <Wrench size={14} /> {t('maint.button')}
      </button>
    );
  return (
    <div className="space-y-2 rounded-lg border border-white/10 bg-black/30 p-3" onClick={(e) => e.stopPropagation()}>
      <p className="text-xs text-[#bac9cc]">{t('maint.explain')}</p>
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={500}
        placeholder={t('maint.note')}
        className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#ff9f43]"
      />
      <div className="flex gap-2">
        <button
          disabled={step === 'busy'}
          onClick={submit}
          className="flex-1 py-1.5 rounded-lg bg-[#ff9f43] text-[#0e0e0e] text-xs font-bold disabled:opacity-50"
        >
          {t('maint.confirm')}
        </button>
        <button onClick={() => setStep('idle')} className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-[#bac9cc]">
          {t('drawer.cancel')}
        </button>
      </div>
      {error && <p className="text-xs text-[#ffb4ab]">{error}</p>}
    </div>
  );
}
