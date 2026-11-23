import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthProvider, useAuth } from './auth';
import { session } from './api';

// tell React this test drives updates with act()
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  session.set(null);
});

const ME = { id: 'u1', username: 'admin', full_name: 'Owner', role: 'owner_admin' };

function mount() {
  const seen: { user: unknown; loading: boolean }[] = [];
  function Probe() {
    const { user, loading } = useAuth();
    seen.push({ user, loading });
    return null;
  }
  const root = createRoot(document.createElement('div'));
  act(() => root.render(createElement(AuthProvider, null, createElement(Probe))));
  return { seen, root };
}

describe('session restore', () => {
  it('keeps the saved sign-in when the server is slow or down, and retries', async () => {
    vi.useFakeTimers();
    session.set('tok');
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('network down'))
      .mockResolvedValueOnce(new Response('busy', { status: 503 }))
      .mockResolvedValue(new Response(JSON.stringify(ME), { status: 200 }));
    const { seen, root } = mount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(session.token).toBe('tok');
    expect(seen.at(-1)).toEqual({ user: ME, loading: false });
    act(() => root.unmount());
  });

  it('signs out only when the server rejects the session (401)', async () => {
    session.set('expired');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));
    const { seen, root } = mount();
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(session.token).toBeNull();
    expect(seen.at(-1)).toEqual({ user: null, loading: false });
    act(() => root.unmount());
  });
});
