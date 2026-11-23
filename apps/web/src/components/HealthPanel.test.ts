import { describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import HealthPanel from './HealthPanel';
import { translate, type MsgKey } from '../lib/i18n';
import type { SystemHealth } from '../lib/api';

// every code the API can return (apps/api/app/routers/system.py)
const CODES = [
  'db_ok', 'db_slow', 'db_down', 'link_ok', 'link_stale', 'link_never', 'loop_ok', 'loop_starting',
  'loop_errors', 'loop_stuck', 'ai_ok', 'ai_degraded', 'weather_healthy', 'weather_degraded',
  'weather_unavailable', 'weather_unknown', 'disk_ok', 'disk_warn', 'disk_fail', 'disk_unknown',
];

describe('health panel', () => {
  it('has Arabic and English text for every check code', () => {
    for (const c of CODES) {
      const key = `health.code.${c}` as MsgKey;
      expect(translate('ar', key), c).not.toBe(key);
      expect(translate('en', key), c).not.toBe(key);
    }
  });

  it('shows each check with what to do', () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    const data: SystemHealth = {
      status: 'fail',
      version: '0.4.0',
      uptime_sec: 3700,
      checked_at: '2026-11-23T12:00:00Z',
      checks: [
        { key: 'database', status: 'ok', code: 'db_ok', detail: { ms: 1.2, journal: 'wal' } },
        { key: 'controller', status: 'fail', code: 'link_stale', detail: { age_sec: 42, source: 'simulator' } },
      ],
    };
    const el = document.createElement('div');
    const root = createRoot(el);
    act(() => root.render(createElement(HealthPanel, { initial: data, onClose: () => {} })));
    expect(el.querySelector('[data-testid="health-controller"]')?.textContent).toContain(translate('ar', 'health.code.link_stale' as MsgKey));
    expect(el.textContent).toContain('42 s');
    act(() => root.unmount());
    vi.restoreAllMocks();
  });
});
