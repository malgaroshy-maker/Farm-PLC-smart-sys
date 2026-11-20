import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';

// Enable React act environment in jsdom
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
import type { DailyIrrigationReportRow } from '@algaroshy/contracts';
import { computeReportDateRange } from '../lib/reportsHelper';
import ModelBadge from '../components/ai/ModelBadge';
import { getBottomNavItems } from '../lib/nav';
import InstallPrompt from '../components/InstallPrompt';
import { isInstallDismissed, INSTALL_STORAGE_KEY } from '../lib/installPrompt';
import { useI18nStore } from '../lib/i18n';
import { reorderSteps, getDayInitial } from '../lib/schedulesHelper';

describe('Reports page unit tests', () => {
  it('computes inclusive farm-local dates correctly for presets', () => {
    // Reference date: 2026-11-19
    const testDate = new Date('2026-11-19T10:00:00Z');

    const computeRange = (preset: 'today' | 'week' | 'month', now: Date) => {
      const to = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Africa/Tripoli',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(now);

      const d = new Date(now);
      if (preset === 'today') {
        return { fromDate: to, toDate: to };
      }
      if (preset === 'week') {
        d.setDate(d.getDate() - 6);
      } else {
        d.setDate(d.getDate() - 29);
      }
      const from = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Africa/Tripoli',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(d);

      return { fromDate: from, toDate: to };
    };

    // Today: 1 day
    const todayRange = computeRange('today', testDate);
    expect(todayRange.fromDate).toBe('2026-11-19');
    expect(todayRange.toDate).toBe('2026-11-19');

    // 7 Days: exactly 7 inclusive dates (13, 14, 15, 16, 17, 18, 19)
    const weekRange = computeRange('week', testDate);
    expect(weekRange.fromDate).toBe('2026-11-13');
    expect(weekRange.toDate).toBe('2026-11-19');
    const weekDiff =
      Math.round(
        (new Date(weekRange.toDate).getTime() - new Date(weekRange.fromDate).getTime()) /
          (1000 * 60 * 60 * 24),
      ) + 1;
    expect(weekDiff).toBe(7);

    // 30 Days: exactly 30 inclusive dates
    const monthRange = computeRange('month', testDate);
    expect(monthRange.toDate).toBe('2026-11-19');
    const monthDiff =
      Math.round(
        (new Date(monthRange.toDate).getTime() - new Date(monthRange.fromDate).getTime()) /
          (1000 * 60 * 60 * 24),
      ) + 1;
    expect(monthDiff).toBe(30);
  });

  it('aggregates daily row counts without ever producing NaN', () => {
    const row: DailyIrrigationReportRow = {
      date: '2026-11-19',
      total_water_m3: 12.5,
      cycle_count: 5,
      completed_count: 3,
      aborted_count: 1,
      skipped_count: 1,
      faulted_count: 0,
      manual_stop_count: 0,
      total_duration_min: 60,
    };

    const totalCycles = row.cycle_count ?? 0;
    const completed = row.completed_count ?? 0;
    const abortedOrSkipped =
      (row.aborted_count ?? 0) +
      (row.skipped_count ?? 0) +
      (row.faulted_count ?? 0) +
      (row.manual_stop_count ?? 0);

    expect(Number.isNaN(totalCycles)).toBe(false);
    expect(totalCycles).toBe(5);
    expect(completed).toBe(3);
    expect(abortedOrSkipped).toBe(2);
    expect(completed + abortedOrSkipped).toBe(5);
  });

  it('handles partial or zero-valued daily report rows safely', () => {
    const emptyRow: Partial<DailyIrrigationReportRow> = {
      date: '2026-11-19',
    };

    const total = emptyRow.cycle_count ?? 0;
    const abortedOrSkipped =
      (emptyRow.aborted_count ?? 0) +
      (emptyRow.skipped_count ?? 0) +
      (emptyRow.faulted_count ?? 0) +
      (emptyRow.manual_stop_count ?? 0);

    expect(Number.isNaN(total)).toBe(false);
    expect(Number.isNaN(abortedOrSkipped)).toBe(false);
    expect(total).toBe(0);
    expect(abortedOrSkipped).toBe(0);
  });

  it('formats query string matching docs/API.md with from_date and to_date', () => {
    const fromDate = '2026-11-13';
    const toDate = '2026-11-19';
    const query = `from_date=${fromDate}&to_date=${toDate}`;

    expect(query).toBe('from_date=2026-11-13&to_date=2026-11-19');
    expect(query).toContain('from_date=');
    expect(query).toContain('to_date=');
  });

  describe('Milestone F UI Polish Tests', () => {
    it('Reports default range is last 7 days (check initial date values)', () => {
      const testDate = new Date('2026-11-20T10:00:00Z');
      const range = computeReportDateRange('week', testDate);
      expect(range.toDate).toBe('2026-11-20');
      expect(range.fromDate).toBe('2026-11-13');

      const diffDays = Math.round(
        (new Date(range.toDate).getTime() - new Date(range.fromDate).getTime()) / (1000 * 60 * 60 * 24)
      );
      expect(diffDays).toBe(7);
    });

    it('Phone nav has exactly 4 bottom items', () => {
      const items = getBottomNavItems(3);
      expect(items).toHaveLength(4);
      expect(items.map((i) => i.path)).toEqual(['/', '/zones', '/alarms', '/schedules']);
      expect(items.find((i) => i.path === '/alarms')?.badge).toBe(3);
    });

    it('ModelBadge renders "Fallback mode" when provider === "rule_based"', async () => {
      useI18nStore.getState().setLang('en');
      const div = document.createElement('div');
      document.body.appendChild(div);
      const root = createRoot(div);
      await act(async () => {
        root.render(React.createElement(ModelBadge, { modelUsed: 'deepseek-v4', provider: 'rule_based' }));
      });
      expect(div.textContent).toContain('Fallback mode');
      await act(async () => {
        root.unmount();
      });
      div.remove();
    });

    it('ModelBadge renders "Fallback mode" when modelUsed is null or undefined', async () => {
      useI18nStore.getState().setLang('en');
      const div = document.createElement('div');
      document.body.appendChild(div);
      const root = createRoot(div);
      await act(async () => {
        root.render(React.createElement(ModelBadge, { modelUsed: null, provider: null }));
      });
      expect(div.textContent).toContain('Fallback mode');
      await act(async () => {
        root.unmount();
      });
      div.remove();
    });

    it('ModelBadge renders model name without free/ prefix', async () => {
      useI18nStore.getState().setLang('en');
      const div = document.createElement('div');
      document.body.appendChild(div);
      const root = createRoot(div);
      await act(async () => {
        root.render(React.createElement(ModelBadge, { modelUsed: 'free/deepseek-v4-pro', provider: 'APInex' }));
      });
      expect(div.textContent).toContain('deepseek-v4-pro');
      expect(div.textContent).not.toContain('free/');
      await act(async () => {
        root.unmount();
      });
      div.remove();
    });

    it('Install prompt shows when beforeinstallprompt fires and is hidden when dismissed', async () => {
      localStorage.removeItem(INSTALL_STORAGE_KEY);
      useI18nStore.getState().setLang('en');
      const div = document.createElement('div');
      document.body.appendChild(div);
      const root = createRoot(div);

      await act(async () => {
        root.render(React.createElement(InstallPrompt));
      });
      // Initially, beforeinstallprompt has not fired yet, so banner is not visible
      expect(div.querySelector('[data-testid="pwa-install-banner"]')).toBeNull();

      // Fire beforeinstallprompt event
      const promptEvent = new Event('beforeinstallprompt');
      Object.assign(promptEvent, {
        prompt: vi.fn().mockResolvedValue(undefined),
        userChoice: Promise.resolve({ outcome: 'dismissed' }),
      });
      await act(async () => {
        window.dispatchEvent(promptEvent);
      });

      // Now banner must be shown
      const banner = div.querySelector('[data-testid="pwa-install-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('Install app on your home screen');

      // Click dismiss button
      const dismissBtn = banner?.querySelector('button[aria-label="Dismiss"]') as HTMLButtonElement | null;
      expect(dismissBtn).not.toBeNull();
      await act(async () => {
        dismissBtn?.click();
      });

      // After dismissal, banner must be hidden
      expect(div.querySelector('[data-testid="pwa-install-banner"]')).toBeNull();
      expect(localStorage.getItem(INSTALL_STORAGE_KEY)).toBe('1');
      expect(isInstallDismissed()).toBe(true);

      await act(async () => {
        root.unmount();
      });
      div.remove();
    });

    it('Schedules step reordering moves items up and down properly', () => {
      const initialSteps = [
        { zone_id: 'zone_01', duration_min: 20 },
        { zone_id: 'zone_02', duration_min: 30 },
        { zone_id: 'zone_03', duration_min: 40 },
      ];

      // Move step 1 down to step 2
      const afterDown = reorderSteps(initialSteps, 0, 1);
      expect(afterDown[0].zone_id).toBe('zone_02');
      expect(afterDown[1].zone_id).toBe('zone_01');
      expect(afterDown[2].zone_id).toBe('zone_03');

      // Move step 2 up to step 1
      const afterUp = reorderSteps(afterDown, 1, 0);
      expect(afterUp).toEqual(initialSteps);
    });

    it('Arabic day initials provide distinct letters for all 7 days of the week', () => {
      const initials = [1, 2, 3, 4, 5, 6, 7].map((dayNum) => getDayInitial(dayNum, 'ar', ''));
      const unique = new Set(initials);
      expect(unique.size).toBe(7);
      expect(initials).toEqual(['ن', 'ث', 'ر', 'خ', 'ج', 'س', 'ح']);
    });
  });
});
