/**
 * Presenter mode: technical screens (Simulator, fault injection) are hidden from
 * owners/investors and revealed by an admin when talking to engineers.
 * Per-viewer convenience, kept in localStorage.
 */
import { create } from 'zustand';

const KEY = 'farm.presenter';

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export const usePresenter = create<{ on: boolean; toggle: () => void }>((set, get) => ({
  on: read(),
  toggle() {
    const on = !get().on;
    try {
      localStorage.setItem(KEY, on ? '1' : '0');
    } catch {
      /* ignore */
    }
    set({ on });
  },
}));
