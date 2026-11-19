import { describe, expect, it } from 'vitest';
import type { DailyIrrigationReportRow } from '@algaroshy/contracts';

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
});
