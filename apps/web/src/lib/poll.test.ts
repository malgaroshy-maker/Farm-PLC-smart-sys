import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { __resetPolls, __setPollFetcher, usePoll } from './poll';

let visibility: DocumentVisibilityState = 'visible';

function Probe({ path, ms, out }: { path: string; ms: number; out: unknown[] }) {
  const d = usePoll<number>(path, ms);
  out.push(d);
  return null;
}

describe('shared polling', () => {
  let calls: string[];
  beforeEach(() => {
    vi.useFakeTimers();
    calls = [];
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
    __resetPolls();
    __setPollFetcher(async (p) => {
      calls.push(p);
      return calls.length;
    });
  });
  afterEach(() => {
    __resetPolls();
    vi.useRealTimers();
  });

  it('two cards on the same path make one request per interval', async () => {
    const out: unknown[] = [];
    const root = createRoot(document.createElement('div'));
    act(() =>
      root.render([
        createElement(Probe, { key: 'a', path: '/x', ms: 1000, out }),
        createElement(Probe, { key: 'b', path: '/x', ms: 1000, out }),
      ]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(calls).toEqual(['/x']);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(calls.length).toBe(4); // t=0, 1s, 2s, 3s — not doubled
    act(() => root.unmount());
  });

  it('pauses while the tab is hidden and refreshes when visible again', async () => {
    const out: unknown[] = [];
    const root = createRoot(document.createElement('div'));
    act(() => root.render(createElement(Probe, { path: '/y', ms: 1000, out })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(calls.length).toBe(1);
    visibility = 'hidden';
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(calls.length).toBe(1); // nothing is fetched while hidden
    visibility = 'visible';
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(calls.length).toBe(2); // immediate refresh on return
    act(() => root.unmount());
  });

  it('stops polling when the last subscriber unmounts', async () => {
    const out: unknown[] = [];
    const root = createRoot(document.createElement('div'));
    act(() => root.render(createElement(Probe, { path: '/z', ms: 1000, out })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    act(() => root.unmount());
    const n = calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(calls.length).toBe(n);
  });
});
