import { useState, useEffect, useRef } from 'react';
import { Check, X, RotateCcw } from 'lucide-react';
import { useAuth } from '../../lib/auth';
import { useT, pickName, type MsgKey } from '../../lib/i18n';
import { approveSuggestion, rejectSuggestion, type AdvisorSuggestion } from '../../lib/api';
import { AiSparklesIcon, WeatherIcon } from '../icons/FarmIcons';

interface SuggestionCardProps {
  suggestion: AdvisorSuggestion;
  onStatusChange?: (updated: AdvisorSuggestion) => void;
}

export default function SuggestionCard({ suggestion, onStatusChange }: SuggestionCardProps) {
  const { can } = useAuth();
  const { t, lang } = useT();
  const canAct = can('owner_admin', 'operator');

  const [overrideStatus, setOverrideStatus] = useState<AdvisorSuggestion['status'] | null>(null);
  const status = overrideStatus ?? suggestion.status;
  const [busy, setBusy] = useState(false);
  const [showUndoToast, setShowUndoToast] = useState(false);
  const [undoSeconds, setUndoSeconds] = useState(5);
  const undoTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (undoTimerRef.current) clearInterval(undoTimerRef.current);
    };
  }, []);

  const handleApprove = async () => {
    if (!canAct || busy) return;
    setBusy(true);

    try {
      await approveSuggestion(suggestion.id);
      const updated: AdvisorSuggestion = { ...suggestion, status: 'approved' };
      setOverrideStatus('approved');
      onStatusChange?.(updated);

      // Start 5-second undo toast countdown
      setShowUndoToast(true);
      setUndoSeconds(5);

      if (undoTimerRef.current) clearInterval(undoTimerRef.current);
      const startTime = Date.now();

      undoTimerRef.current = setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        const remaining = Math.max(0, 5 - Math.floor(elapsed));
        setUndoSeconds(remaining);

        if (remaining <= 0) {
          if (undoTimerRef.current) clearInterval(undoTimerRef.current);
          setShowUndoToast(false);
        }
      }, 500);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!canAct || busy) return;
    setBusy(true);

    try {
      await rejectSuggestion(suggestion.id);
      const updated: AdvisorSuggestion = { ...suggestion, status: 'rejected' };
      setOverrideStatus('rejected');
      onStatusChange?.(updated);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Rejection failed');
    } finally {
      setBusy(false);
    }
  };

  const handleUndo = async () => {
    if (undoTimerRef.current) clearInterval(undoTimerRef.current);
    setShowUndoToast(false);
    setBusy(true);

    try {
      // Revert to pending
      const updated: AdvisorSuggestion = { ...suggestion, status: 'pending' };
      setOverrideStatus('pending');
      onStatusChange?.(updated);
    } catch {
      // Ignore
    } finally {
      setBusy(false);
    }
  };

  if (status === 'rejected' || status === 'expired') return null;

  const actionColorMap: Record<AdvisorSuggestion['action'], { bg: string; text: string; border: string }> = {
    skip: { bg: 'bg-[#ff5449]/15', text: 'text-[#ffb4ab]', border: 'border-[#ff5449]/30' },
    shorten: { bg: 'bg-[#ffeb3b]/15', text: 'text-[#ffeb3b]', border: 'border-[#ffeb3b]/30' },
    extend: { bg: 'bg-[#00e5ff]/15', text: 'text-[#00e5ff]', border: 'border-[#00e5ff]/30' },
    reschedule: { bg: 'bg-[#b98cff]/15', text: 'text-[#b98cff]', border: 'border-[#b98cff]/30' },
  };

  const actionStyle = actionColorMap[suggestion.action] ?? actionColorMap.shorten;
  const reasonText = pickName(lang, suggestion.reason, suggestion.reason_ar);
  const progName = pickName(lang, suggestion.program_name, suggestion.program_name_ar) || suggestion.program_id || '';

  return (
    <div className="panel p-3.5 sm:p-4 space-y-3 relative overflow-hidden border-[#00e5ff]/20 bg-gradient-to-br from-[#161d20]/80 via-[#141416]/90 to-[#101416]/90 shadow-md">
      {/* Header bar: Weather & Action Badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="p-1.5 rounded-lg bg-white/5 text-[#00e5ff] shrink-0">
            <WeatherIcon condition={suggestion.weather_summary?.condition} size={18} />
          </span>
          <div className="min-w-0">
            <div className="text-xs font-bold text-[#e5e2e1] truncate">{progName}</div>
            <div className="text-[11px] text-[#849396] font-mono">{suggestion.effective_date}</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${actionStyle.bg} ${actionStyle.text} ${actionStyle.border}`}
          >
            {t(`advisor.action.${suggestion.action}` as MsgKey)}
            {suggestion.adjustment_pct != null && ` ${suggestion.adjustment_pct > 0 ? '+' : ''}${suggestion.adjustment_pct}%`}
          </span>
        </div>
      </div>

      {/* Reason narrative */}
      <p className="text-xs text-[#bac9cc] leading-relaxed">
        {reasonText}
      </p>

      {/* Provider badge & Expiration info */}
      <div className="flex items-center justify-between text-[11px] text-[#849396] pt-1 border-t border-white/5">
        <span className="flex items-center gap-1 text-[#00e5ff]">
          <AiSparklesIcon size={12} />
          {suggestion.is_fallback ? t('ai.ruleBasedLabel') : suggestion.model || suggestion.provider || 'APInex'}
        </span>
        {suggestion.expires_at && (
          <span className="font-mono">
            {t('advisor.expiresIn')} {suggestion.expires_at.slice(11, 16)}
          </span>
        )}
      </div>

      {/* Action Buttons (Operator+) */}
      {canAct && status === 'pending' && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={handleApprove}
            disabled={busy}
            className="flex-1 py-1.5 px-3 rounded-xl bg-[#00e5ff] hover:bg-[#00e5ff]/90 text-[#0e0e0e] text-xs font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <Check size={14} />
            <span>{t('advisor.approve')}</span>
          </button>
          <button
            onClick={handleReject}
            disabled={busy}
            className="py-1.5 px-3 rounded-xl border border-white/10 hover:bg-white/5 text-[#849396] hover:text-[#e5e2e1] text-xs font-medium flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
          >
            <X size={14} />
            <span>{t('advisor.reject')}</span>
          </button>
        </div>
      )}

      {/* 5-second Undo Toast when Approved */}
      {showUndoToast && (
        <div className="mt-2 p-2.5 rounded-xl bg-[#00e5ff]/15 border border-[#00e5ff]/40 flex items-center justify-between gap-2 animate-fadeIn">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-ping" />
            <span className="text-xs text-[#e5e2e1] font-medium truncate">
              {t('advisor.approved')} ({undoSeconds}s)
            </span>
          </div>
          <button
            onClick={handleUndo}
            className="px-2.5 py-1 rounded-lg bg-[#141416] hover:bg-black text-[#00e5ff] border border-[#00e5ff]/30 text-xs font-bold flex items-center gap-1 shrink-0 transition-colors"
          >
            <RotateCcw size={13} />
            <span>{t('advisor.undo')}</span>
          </button>
        </div>
      )}
    </div>
  );
}
