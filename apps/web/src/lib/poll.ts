/**
 * Shared polling (Milestone G1).
 *
 * Every component that polls the same path shares ONE request loop:
 *  - duplicate cards (e.g. the phone and desktop copies of a card) fetch once;
 *  - the loop runs at the fastest interval any subscriber asked for;
 *  - polling pauses while the tab is hidden and refreshes as soon as it is visible again;
 *  - a new subscriber gets the last value immediately (no empty flash).
 */
import { useSyncExternalStore } from 'react';
import { apiFetch } from './api';

type Entry = {
  data: unknown;
  intervals: Map<symbol, number>;
  listeners: Set<() => void>;
  timer: ReturnType<typeof setTimeout> | null;
  inflight: boolean;
  lastFetch: number;
};

const entries = new Map<string, Entry>();
let fetcher: (path: string) => Promise<unknown> = (p) => apiFetch(p);

/** Test hook: replace the network call. */
export function __setPollFetcher(f: (path: string) => Promise<unknown>) {
  fetcher = f;
}

function hidden(): boolean {
  return typeof document !== 'undefined' && document.visibilityState === 'hidden';
}

function minInterval(e: Entry): number {
  return Math.min(...e.intervals.values());
}

function schedule(path: string, e: Entry, delay: number) {
  if (e.timer) clearTimeout(e.timer);
  e.timer = setTimeout(() => void tick(path), delay);
}

async function tick(path: string) {
  const e = entries.get(path);
  if (!e || e.intervals.size === 0) return;
  if (hidden()) {
    e.timer = null; // resumed by the visibilitychange listener
    return;
  }
  if (!e.inflight) {
    e.inflight = true;
    try {
      e.data = await fetcher(path);
      e.lastFetch = Date.now();
      e.listeners.forEach((l) => l());
    } catch {
      /* keep the last good value; the next tick retries */
    } finally {
      e.inflight = false;
    }
  }
  if (entries.get(path) === e && e.intervals.size > 0) schedule(path, e, minInterval(e));
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (hidden()) return;
    for (const [path, e] of entries) {
      if (e.intervals.size === 0) continue;
      const due = Date.now() - e.lastFetch >= minInterval(e);
      schedule(path, e, due ? 0 : minInterval(e) - (Date.now() - e.lastFetch));
    }
  });
}

function subscribe(path: string, ms: number, listener: () => void): () => void {
  let e = entries.get(path);
  if (!e) {
    e = { data: null, intervals: new Map(), listeners: new Set(), timer: null, inflight: false, lastFetch: 0 };
    entries.set(path, e);
  }
  const id = Symbol(path);
  const wasIdle = e.intervals.size === 0;
  const before = wasIdle ? Infinity : minInterval(e);
  e.intervals.set(id, ms);
  e.listeners.add(listener);
  if (wasIdle) {
    const age = Date.now() - e.lastFetch;
    schedule(path, e, age >= ms ? 0 : ms - age);
  } else if (ms < before) {
    schedule(path, e, Math.max(0, ms - (Date.now() - e.lastFetch)));
  }
  return () => {
    const cur = entries.get(path);
    if (!cur) return;
    cur.intervals.delete(id);
    cur.listeners.delete(listener);
    if (cur.intervals.size === 0 && cur.timer) {
      clearTimeout(cur.timer);
      cur.timer = null;
    }
  };
}

/** Poll `path` every `ms` (shared, paused while hidden). `null` path = don't poll. */
export function usePoll<T>(path: string | null, ms: number): T | null {
  return useSyncExternalStore(
    (onChange) => (path ? subscribe(path, ms, onChange) : () => {}),
    () => (path ? ((entries.get(path)?.data as T | undefined) ?? null) : null),
    () => null,
  );
}

/** Test helper: forget all shared state. */
export function __resetPolls() {
  for (const e of entries.values()) if (e.timer) clearTimeout(e.timer);
  entries.clear();
}
