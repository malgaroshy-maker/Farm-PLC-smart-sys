import { useState } from 'react';
import { Pause, Play, StepForward, Compass } from 'lucide-react';
import { useClockStore } from '../../lib/clock';
import { useT } from '../../lib/i18n';

const SPEEDS = [1, 10, 60, 360];
const PRESETS = [
  { time: '05:30', key: 'clock.dawn' as const },
  { time: '12:00', key: 'clock.noon' as const },
  { time: '18:30', key: 'clock.sunset' as const },
  { time: '22:00', key: 'clock.night' as const },
];

export default function ClockHeaderChip() {
  const { t } = useT();
  const speed = useClockStore((s) => s.speed);
  const paused = useClockStore((s) => s.paused);
  const setSpeed = useClockStore((s) => s.setSpeed);
  const togglePause = useClockStore((s) => s.togglePause);
  const step = useClockStore((s) => s.step);
  const jumpTo = useClockStore((s) => s.jumpTo);

  const [showJump, setShowJump] = useState(false);
  const [customTime, setCustomTime] = useState('');
  const [busy, setBusy] = useState(false);

  const handleAction = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  const handleCustomJump = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customTime.trim()) return;
    await handleAction(() => jumpTo(customTime.trim()));
    setShowJump(false);
    setCustomTime('');
  };

  return (
    <div className="relative hidden md:flex items-center gap-1 bg-[#18181b]/90 border border-white/10 rounded-xl p-1 text-xs backdrop-blur-md shadow-inner">
      {/* Play / Pause button */}
      <button
        onClick={() => handleAction(togglePause)}
        disabled={busy}
        title={paused ? t('clock.play') : t('clock.pause')}
        className={`p-1.5 rounded-lg transition-colors ${
          paused
            ? 'bg-[#ff9f43]/20 text-[#ff9f43] hover:bg-[#ff9f43]/30'
            : 'text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1]'
        }`}
      >
        {paused ? <Play size={13} fill="currentColor" /> : <Pause size={13} fill="currentColor" />}
      </button>

      {/* Speed buttons */}
      <div className="flex items-center gap-0.5 bg-black/30 rounded-lg p-0.5 border border-white/5">
        {SPEEDS.map((s) => {
          const active = !paused && speed === s;
          return (
            <button
              key={s}
              onClick={() => handleAction(() => setSpeed(s))}
              disabled={busy}
              className={`px-1.5 py-0.5 rounded text-[11px] font-mono font-bold transition-all ${
                active
                  ? 'bg-[#00e5ff] text-[#0e0e0e] shadow-[0_0_8px_rgba(0,229,255,0.4)]'
                  : 'text-[#849396] hover:text-[#e5e2e1] hover:bg-white/5'
              }`}
            >
              {s}×
            </button>
          );
        })}
      </div>

      {/* Step +1 min */}
      <button
        onClick={() => handleAction(() => step(1))}
        disabled={busy}
        title={t('clock.step')}
        className="flex items-center gap-1 px-1.5 py-1 rounded-lg text-[#849396] hover:text-[#e5e2e1] hover:bg-white/10 text-[11px] font-mono"
      >
        <StepForward size={12} />
        <span>+1m</span>
      </button>

      {/* Jump Menu Trigger */}
      <button
        onClick={() => setShowJump(!showJump)}
        title={t('clock.jump')}
        className={`p-1.5 rounded-lg transition-colors ${
          showJump ? 'bg-[#00e5ff]/20 text-[#00e5ff]' : 'text-[#849396] hover:text-[#e5e2e1] hover:bg-white/10'
        }`}
      >
        <Compass size={13} />
      </button>

      {/* Jump Popover */}
      {showJump && (
        <div className="absolute top-full mt-2 end-0 z-50 w-56 p-3 rounded-xl bg-[#141416]/95 border border-white/15 shadow-2xl backdrop-blur-xl space-y-2.5">
          <div className="text-[11px] font-bold text-[#849396] flex items-center justify-between">
            <span>{t('clock.jump')}</span>
            <span className="text-[10px] text-[#ff9f43]">UTC+2</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p.time}
                onClick={async () => {
                  await handleAction(() => jumpTo(p.time));
                  setShowJump(false);
                }}
                className="px-2 py-1.5 rounded-lg bg-white/5 hover:bg-[#00e5ff]/15 hover:text-[#00e5ff] text-[11px] font-mono text-center border border-white/5 transition-colors"
              >
                {t(p.key)}
              </button>
            ))}
          </div>
          <form onSubmit={handleCustomJump} className="flex items-center gap-1.5 pt-1 border-t border-white/10">
            <input
              type="text"
              placeholder="05:30"
              value={customTime}
              onChange={(e) => setCustomTime(e.target.value)}
              className="flex-1 min-w-0 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs font-mono text-[#e5e2e1] focus:border-[#00e5ff] focus:outline-none"
            />
            <button
              type="submit"
              className="px-2.5 py-1 rounded-lg bg-[#00e5ff]/20 text-[#00e5ff] hover:bg-[#00e5ff]/30 text-xs font-bold font-sans"
            >
              {t('clock.jumpAction')}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
