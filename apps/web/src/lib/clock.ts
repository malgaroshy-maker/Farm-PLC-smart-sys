/**
 * Virtual farm clock store and hooks (SIMULATION_TIME.md).
 * Synchronized with the API FarmClock via WebSocket ('clock.changed' and 'state.snapshot')
 * and local sub-second tick interpolation.
 */
import { useEffect, useState } from 'react';
import { create } from 'zustand';
import type { FarmClockState } from '@algaroshy/contracts';
import { apiFetch } from './api';

export interface ClockData {
  mode?: string;
  speed?: number;
  paused?: boolean;
  clock_mode?: string;
  clock_paused?: boolean;
  farm_now?: string;
  real_now?: string;
}

interface ClockStore {
  mode: 'real' | 'sim';
  speed: number;
  paused: boolean;
  anchorSimMs: number;
  clientRecvMs: number;
  isSimulated: boolean;
  sync: (data: ClockData) => void;
  fetchClock: () => Promise<void>;
  setSpeed: (speed: number) => Promise<void>;
  togglePause: () => Promise<void>;
  step: (stepMin?: number) => Promise<void>;
  jumpTo: (timeStr: string) => Promise<void>;
  resetToReal: () => Promise<void>;
}

export const useClockStore = create<ClockStore>((set, get) => ({
  mode: 'real',
  speed: 1.0,
  paused: false,
  anchorSimMs: Date.now(),
  clientRecvMs: typeof performance !== 'undefined' ? performance.now() : Date.now(),
  isSimulated: false,

  sync(data) {
    const mode = (data.clock_mode || data.mode || 'real') as 'real' | 'sim';
    const speed = data.speed !== undefined ? Number(data.speed) : get().speed;
    const paused = data.clock_paused !== undefined ? Boolean(data.clock_paused) : Boolean(data.paused);
    let simMs = get().anchorSimMs;
    if (data.farm_now) {
      const s = data.farm_now.endsWith('Z') ? data.farm_now : `${data.farm_now}Z`;
      const parsed = Date.parse(s);
      if (!Number.isNaN(parsed)) simMs = parsed;
    }
    const isSimulated = mode === 'sim' || speed !== 1.0 || paused;
    set({
      mode,
      speed,
      paused,
      anchorSimMs: simMs,
      clientRecvMs: typeof performance !== 'undefined' ? performance.now() : Date.now(),
      isSimulated,
    });
  },

  async fetchClock() {
    try {
      const res = await apiFetch<FarmClockState>('/api/v1/sim/clock');
      get().sync(res);
    } catch {
      /* ignore if offline */
    }
  },

  async setSpeed(speed: number) {
    const res = await apiFetch<FarmClockState>('/api/v1/sim/clock', {
      method: 'POST',
      body: JSON.stringify({ speed }),
    });
    get().sync(res);
  },

  async togglePause() {
    const res = await apiFetch<FarmClockState>('/api/v1/sim/clock', {
      method: 'POST',
      body: JSON.stringify({ pause: !get().paused }),
    });
    get().sync(res);
  },

  async step(stepMin = 1) {
    const res = await apiFetch<FarmClockState>('/api/v1/sim/clock', {
      method: 'POST',
      body: JSON.stringify({ step_min: stepMin }),
    });
    get().sync(res);
  },

  async jumpTo(timeStr: string) {
    const res = await apiFetch<FarmClockState>('/api/v1/sim/clock', {
      method: 'POST',
      body: JSON.stringify({ jump_to: timeStr }),
    });
    get().sync(res);
  },

  async resetToReal() {
    const res = await apiFetch<FarmClockState>('/api/v1/sim/clock', {
      method: 'POST',
      body: JSON.stringify({ real: true, confirm: true }),
    });
    get().sync(res);
  },
}));

export function computeFarmNow(): Date {
  const { mode, paused, speed, anchorSimMs, clientRecvMs } = useClockStore.getState();
  if (mode === 'real') return new Date();
  if (paused) return new Date(anchorSimMs);
  const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const elapsed = (now - clientRecvMs) * speed;
  return new Date(anchorSimMs + elapsed);
}

export function formatFarmClock(date: Date, lang: string): string {
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-LY-u-nu-latn' : 'en-GB', {
    timeZone: 'Africa/Tripoli',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).format(date);
}

export function farmHourAndMonth(date: Date): { hour: number; month: number } {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Tripoli',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: 'numeric',
    hourCycle: 'h23',
  }).formatToParts(date);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return {
    hour: get('hour') + get('minute') / 60 + get('second') / 3600,
    month: get('month') || date.getMonth() + 1,
  };
}

/** Hook ticking the current farm local time. */
export function useFarmClock(lang: string = 'ar') {
  const mode = useClockStore((s) => s.mode);
  const speed = useClockStore((s) => s.speed);
  const paused = useClockStore((s) => s.paused);
  const isSimulated = useClockStore((s) => s.isSimulated);
  const [farmNow, setFarmNow] = useState<Date>(() => computeFarmNow());

  useEffect(() => {
    const tickInterval = speed >= 60 ? 100 : speed >= 10 ? 250 : 500;
    const id = setInterval(() => {
      setFarmNow(computeFarmNow());
    }, tickInterval);
    return () => clearInterval(id);
  }, [speed, paused, mode]);

  const { hour, month } = farmHourAndMonth(farmNow);
  const formatted = formatFarmClock(farmNow, lang);

  return {
    farmNow,
    speed,
    mode,
    paused,
    isSimulated,
    hour,
    month,
    formatted,
  };
}
