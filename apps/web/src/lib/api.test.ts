import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiFetch, session, wsUrl } from './api';

afterEach(() => {
  vi.restoreAllMocks();
  session.set(null);
});

describe('wsUrl', () => {
  it('uses the page origin and ws scheme by default', () => {
    const url = new URL(wsUrl('tok en'));
    expect(url.protocol).toBe('ws:');
    expect(url.pathname).toBe('/ws');
    expect(url.searchParams.get('token')).toBe('tok en');
  });
});

describe('apiFetch', () => {
  it('sends the bearer token and parses JSON', async () => {
    session.set('abc');
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({ ok: 1 }), { status: 200 }));
    await expect(apiFetch('/api/v1/zones')).resolves.toEqual({ ok: 1 });
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer abc');
  });

  it('surfaces interlock messages and keeps the body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ code: 'max_concurrent_zones', message: 'Max 1 zone', command_id: 'c' }), {
        status: 409,
      }),
    );
    const err = (await apiFetch('/api/v1/commands', { method: 'POST', body: '{}' }).catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe('Max 1 zone');
  });

  it('drops the session and notifies listeners on 401', async () => {
    session.set('expired');
    const onUnauth = vi.fn();
    const off = session.onUnauthorized(onUnauth);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    );
    await expect(apiFetch('/api/v1/zones')).rejects.toThrow('Not authenticated');
    expect(session.token).toBeNull();
    expect(onUnauth).toHaveBeenCalledOnce();
    off();
  });
});
