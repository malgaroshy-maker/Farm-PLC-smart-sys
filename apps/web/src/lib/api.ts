/**
 * Thin fetch wrapper: base URL, bearer token, typed errors.
 *
 * By default the web app talks same-origin (`/api`, `/ws`) and the Vite dev
 * server proxies to the backend, so it also works from a phone on the LAN.
 * Set VITE_API_URL (e.g. http://192.168.1.20:8000) to call the API directly.
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
const TOKEN_KEY = 'farm.token';

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function wsUrl(token: string): string {
  const base = API_BASE || window.location.origin;
  const url = new URL('/ws', base);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('token', token);
  return url.toString();
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — session only */
  }
}

let token: string | null = readStorage(TOKEN_KEY);
const unauthorizedListeners = new Set<() => void>();

export const session = {
  get token() {
    return token;
  },
  set(value: string | null) {
    token = value;
    writeStorage(TOKEN_KEY, value);
  },
  onUnauthorized(fn: () => void) {
    unauthorizedListeners.add(fn);
    return () => unauthorizedListeners.delete(fn);
  },
};

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as { detail?: unknown; message?: unknown };
    if (typeof b.message === 'string') return b.message;
    if (typeof b.detail === 'string') return b.detail;
    if (Array.isArray(b.detail)) return 'Invalid request';
  }
  return `Request failed (${status})`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(apiUrl(path), { ...init, headers });
  const text = await res.text();
  const body: unknown = text ? JSON.parse(text) : null;

  if (!res.ok) {
    if (res.status === 401 && token) {
      session.set(null);
      unauthorizedListeners.forEach((fn) => fn());
    }
    throw new ApiError(res.status, body, errorMessage(body, res.status));
  }
  return body as T;
}
