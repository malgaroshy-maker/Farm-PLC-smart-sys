/**
 * Per-viewer UI preferences: reduce motion and alarm sound mute.
 * Reduce motion starts from the OS setting; both are remembered in localStorage.
 */
import { create } from 'zustand';

function read(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v === '1';
  } catch {
    return fallback;
  }
}

function write(key: string, v: boolean) {
  try {
    localStorage.setItem(key, v ? '1' : '0');
  } catch {
    /* ignore */
  }
}

const osReduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function applyMotion(v: boolean) {
  if (typeof document !== 'undefined') document.documentElement.dataset.reduceMotion = v ? '1' : '0';
}

interface Prefs {
  reduceMotion: boolean;
  muted: boolean;
  toggleMotion: () => void;
  toggleMute: () => void;
}

const initialMotion = read('farm.reduceMotion', !!osReduced);
applyMotion(initialMotion);

export const usePrefs = create<Prefs>((set, get) => ({
  reduceMotion: initialMotion,
  muted: read('farm.muted', false),
  toggleMotion() {
    const v = !get().reduceMotion;
    write('farm.reduceMotion', v);
    applyMotion(v);
    set({ reduceMotion: v });
  },
  toggleMute() {
    const v = !get().muted;
    write('farm.muted', v);
    set({ muted: v });
  },
}));
