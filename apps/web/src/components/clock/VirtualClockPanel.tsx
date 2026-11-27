import { useState } from 'react';
import {
  Clock,
  Play,
  Pause,
  StepForward,
  RotateCcw,
  AlertTriangle,
  Compass,
} from 'lucide-react';
import { useClockStore, useFarmClock } from '../../lib/clock';
import { useT } from '../../lib/i18n';
import { useAuth } from '../../lib/auth';
import SimTimeBadge from './SimTimeBadge';

const SPEEDS = [
  { val: 0, label: '0×' },
  { val: 1, label: '1×' },
  { val: 10, label: '10×' },
  { val: 60, label: '60×' },
  { val: 360, label: '360×' },
];

const PRESETS = [
  { time: '05:30', key: 'clock.dawn' as const },
  { time: '12:00', key: 'clock.noon' as const },
  { time: '18:30', key: 'clock.sunset' as const },
  { time: '22:00', key: 'clock.night' as const },
];

export default function VirtualClockPanel() {
  const { t, lang } = useT();
  const { can } = useAuth();
  const isAdmin = can('owner_admin');

  const speed = useClockStore((s) => s.speed);
  const lockedReal = useClockStore((s) => s.lockedReal);
  const paused = useClockStore((s) => s.paused);
  const isSimulated = useClockStore((s) => s.isSimulated);
  const setSpeed = useClockStore((s) => s.setSpeed);
  const togglePause = useClockStore((s) => s.togglePause);
  const step = useClockStore((s) => s.step);
  const jumpTo = useClockStore((s) => s.jumpTo);
  const resetToReal = useClockStore((s) => s.resetToReal);

  const { formatted, farmNow } = useFarmClock(lang);

  const [customTime, setCustomTime] = useState('');
  const [showConfirmReset, setShowConfirmReset] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const flash = (text: string) => {
    setMsg(text);
    setTimeout(() => setMsg(null), 4000);
  };

  const handleAction = async (fn: () => Promise<void>, successText?: string) => {
    if (!isAdmin || lockedReal) return;
    setBusy(true);
    try {
      await fn();
      if (successText) flash(successText);
    } catch (err) {
      flash(err instanceof Error ? err.message : t('common.actionFailed'));
    } finally {
      setBusy(false);
    }
  };

  const handleJump = async (timeStr: string) => {
    await handleAction(
      () => jumpTo(timeStr),
      `${t('clock.jump')}: ${timeStr}`
    );
  };

  const handleCustomJump = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customTime.trim()) return;
    await handleJump(customTime.trim());
    setCustomTime('');
  };

  const handleConfirmReset = async () => {
    setShowConfirmReset(false);
    await handleAction(
      () => resetToReal(),
      t('clock.realTime')
    );
  };

  return (
    <div className="panel p-5 space-y-5 border border-white/10 bg-[#161618]/90 backdrop-blur-xl relative">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Clock className="text-[#00e5ff]" size={22} />
          <div>
            <h2 className="text-base font-bold text-[#e5e2e1]">{t(lockedReal ? 'clock.plcRealTime' : 'clock.title')}</h2>
            <p className="text-xs text-[#849396]">{t(lockedReal ? 'clock.plcLocked' : 'clock.subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {msg && <span className="font-mono text-xs text-[#ffeb3b]">{msg}</span>}
          <SimTimeBadge />
        </div>
      </div>

      {/* Main Digital Clock Display */}
      <div className="rounded-xl border border-white/10 bg-[#0e0e0e]/80 p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex flex-col items-center sm:items-start">
          <span className="text-xs text-[#849396] uppercase font-mono tracking-wider">
            {lang === 'ar' ? 'توقيت المزرعة (طرابلس)' : 'Farm Local Time (Tripoli)'}
          </span>
          <span
            className={`text-2xl sm:text-3xl font-mono font-bold tracking-tight mt-1 ${
              isSimulated ? 'text-[#ff9f43]' : 'text-[#00e5ff]'
            }`}
            dir="ltr"
          >
            {formatted}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span
            className={`px-2.5 py-1 rounded-md border ${
              paused
                ? 'border-[#ff9f43]/40 bg-[#ff9f43]/15 text-[#ff9f43]'
                : speed > 1
                  ? 'border-[#ff9f43]/30 bg-[#ff9f43]/10 text-[#ff9f43]'
                  : 'border-[#7ee787]/30 bg-[#7ee787]/10 text-[#7ee787]'
            }`}
          >
            {paused ? t('clock.paused') : `${speed}×`}
          </span>
          <span className="text-[#849396]">
            {farmNow.toISOString().slice(11, 19)} UTC
          </span>
        </div>
      </div>

      {/* Controls Grid */}
      <fieldset disabled={lockedReal} className={lockedReal ? 'hidden' : 'grid grid-cols-1 md:grid-cols-2 gap-4'}>
        {/* Play / Pause / Step / Speeds */}
        <div className="space-y-3">
          <label className="text-xs font-bold text-[#bac9cc] block">
            {t('clock.speed')} & {lang === 'ar' ? 'التحكم' : 'Playback'}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleAction(togglePause)}
              disabled={busy || !isAdmin}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-bold text-xs transition-colors border ${
                paused
                  ? 'border-[#00e5ff] bg-[#00e5ff]/20 text-[#00e5ff] hover:bg-[#00e5ff]/30'
                  : 'border-[#ff9f43]/40 bg-[#ff9f43]/15 text-[#ff9f43] hover:bg-[#ff9f43]/25'
              } disabled:opacity-40`}
            >
              {paused ? <Play size={14} /> : <Pause size={14} />}
              <span>{paused ? t('clock.play') : t('clock.pause')}</span>
            </button>

            <button
              onClick={() => handleAction(() => step(1))}
              disabled={busy || !isAdmin}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 text-[#e5e2e1] bg-white/5 text-xs transition-colors disabled:opacity-40"
              title={t('clock.step')}
            >
              <StepForward size={14} />
              <span>{t('clock.step')}</span>
            </button>
          </div>

          <div className="flex flex-wrap gap-1.5 pt-1">
            {SPEEDS.map((s) => {
              const active = (s.val === 0 && paused) || (!paused && speed === s.val);
              return (
                <button
                  key={s.val}
                  onClick={() =>
                    handleAction(() => (s.val === 0 ? togglePause() : setSpeed(s.val)))
                  }
                  disabled={busy || !isAdmin}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all border ${
                    active
                      ? 'border-[#00e5ff] bg-[#00e5ff]/20 text-[#00e5ff]'
                      : 'border-white/10 bg-white/5 text-[#849396] hover:text-[#e5e2e1] hover:bg-white/10'
                  } disabled:opacity-40`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Jump Presets & Custom Jump */}
        <div className="space-y-3">
          <label className="text-xs font-bold text-[#bac9cc] block">
            {t('clock.jump')}
          </label>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.time}
                onClick={() => handleJump(p.time)}
                disabled={busy || !isAdmin}
                className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:border-[#00e5ff]/40 text-xs text-[#e5e2e1] hover:text-[#00e5ff] transition-colors disabled:opacity-40"
              >
                <span>{t(p.key)}</span>
                <span className="font-mono text-[#849396] text-[11px]">{p.time}</span>
              </button>
            ))}
          </div>

          {/* Custom Time Form */}
          <form onSubmit={handleCustomJump} className="flex gap-2">
            <input aria-label={t('clock.customTime')}
              type="text"
              placeholder="HH:MM (e.g. 05:30)"
              value={customTime}
              onChange={(e) => setCustomTime(e.target.value)}
              pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
              title="00:00–23:59"
              disabled={busy || !isAdmin}
              className="flex-1 px-3 py-1.5 rounded-lg border border-white/10 bg-[#0e0e0e] text-xs font-mono text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              dir="ltr"
            />
            <button
              type="submit"
              disabled={busy || !isAdmin || !customTime.trim()}
              className="px-3 py-1.5 rounded-lg border border-[#00e5ff]/40 bg-[#00e5ff]/10 text-[#00e5ff] hover:bg-[#00e5ff]/20 text-xs font-bold transition-colors disabled:opacity-40"
            >
              {t('clock.jumpAction')}
            </button>
          </form>
        </div>
      </fieldset>

      {/* Back to Real Time section */}
      <div className={lockedReal ? 'hidden' : 'pt-2 border-t border-white/10 flex flex-wrap items-center justify-between gap-3'}>
        <div className="text-xs text-[#849396]">
          {isSimulated ? (
            <span className="text-[#ff9f43] flex items-center gap-1.5">
              <Compass size={14} />
              {lang === 'ar'
                ? 'الساعة تعمل حالياً في وضع المحاكاة.'
                : 'Clock is currently running in simulation mode.'}
            </span>
          ) : (
            <span className="text-[#7ee787]">
              ✓ {lang === 'ar' ? 'الساعة متزامنة مع الوقت الفعلي 1×' : 'Clock is synced to real time (1×)'}
            </span>
          )}
        </div>

        {isAdmin && (
          <button
            onClick={() => setShowConfirmReset(true)}
            disabled={busy || !isSimulated}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#ff9f43]/40 text-[#ff9f43] hover:bg-[#ff9f43]/15 text-xs font-bold transition-colors disabled:opacity-30 disabled:pointer-events-none"
          >
            <RotateCcw size={14} />
            <span>{t('clock.realTime')}</span>
          </button>
        )}
      </div>

      {/* Confirmation Modal */}
      {showConfirmReset && !lockedReal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="panel p-6 max-w-md w-full border border-[#ff9f43]/40 bg-[#18181b] shadow-2xl space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-[#ff9f43]/20 text-[#ff9f43] shrink-0">
                <AlertTriangle size={24} />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-[#e5e2e1]">
                  {t('clock.realTime')}
                </h3>
                <p className="text-xs text-[#bac9cc] leading-relaxed">
                  {t('clock.realTimeConfirm')}
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirmReset(false)}
                className="px-4 py-2 rounded-lg border border-white/10 text-xs text-[#849396] hover:text-[#e5e2e1] hover:bg-white/5 transition-colors"
              >
                {t('clock.cancel')}
              </button>
              <button
                type="button"
                onClick={handleConfirmReset}
                className="px-4 py-2 rounded-lg border border-[#ff5449] bg-[#ff5449]/20 text-[#ff5449] hover:bg-[#ff5449]/30 text-xs font-bold transition-colors"
              >
                {t('clock.confirmReset')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
