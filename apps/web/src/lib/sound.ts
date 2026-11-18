/**
 * Alarm chime, synthesized with Web Audio (no sound file to ship or cache).
 * S3 critical: two-tone descending chime; S2 major: single soft tone.
 * Browsers only allow audio after a user gesture, so the context is unlocked
 * on the first click/keypress.
 */
let ctx: AudioContext | null = null;

function context(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!ctx) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
  }
  return ctx;
}

export function unlockAudio() {
  const c = context();
  if (c && c.state === 'suspended') void c.resume();
}

if (typeof window !== 'undefined') {
  const once = () => {
    unlockAudio();
    window.removeEventListener('pointerdown', once);
    window.removeEventListener('keydown', once);
  };
  window.addEventListener('pointerdown', once);
  window.addEventListener('keydown', once);
}

function tone(c: AudioContext, freq: number, start: number, dur: number, gain: number) {
  const osc = c.createOscillator();
  const g = c.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(freq, start);
  g.gain.setValueAtTime(0.0001, start);
  g.gain.exponentialRampToValueAtTime(gain, start + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
  osc.connect(g).connect(c.destination);
  osc.start(start);
  osc.stop(start + dur + 0.05);
}

export function playAlarmChime(severity: 'S2' | 'S3') {
  const c = context();
  if (!c || c.state !== 'running') return;
  const t = c.currentTime + 0.01;
  if (severity === 'S3') {
    tone(c, 880, t, 0.35, 0.18);
    tone(c, 660, t + 0.32, 0.5, 0.18);
  } else {
    tone(c, 740, t, 0.45, 0.12);
  }
}
