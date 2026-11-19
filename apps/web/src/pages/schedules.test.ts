import { describe, expect, it } from 'vitest';
import { useClockStore, computeFarmNow, parseUtcDate } from '../lib/clock';

describe('schedules & next irrigation unit tests', () => {
  it('parses and formats weekday masks correctly', () => {
    const parseDays = (maskStr: string | undefined): number[] => {
      if (!maskStr) return [1, 2, 3, 4, 5, 6, 7];
      return maskStr
        .split(',')
        .map((s) => Number(s.trim()))
        .filter((n) => n >= 1 && n <= 7);
    };

    const formatDays = (days: number[]): string => {
      return [...days].sort((a, b) => a - b).join(',');
    };

    expect(parseDays('1,3,5')).toEqual([1, 3, 5]);
    expect(parseDays('')).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(formatDays([5, 1, 3])).toBe('1,3,5');
  });

  it('computes countdown accurately with simulated farm clock', () => {
    // Farm clock set to 07:45:00 UTC
    useClockStore.getState().sync({
      mode: 'sim',
      speed: 1.0,
      paused: true,
      farm_now: '2026-11-19T07:45:00Z',
    });

    const now = computeFarmNow();
    const scheduledStartIso = '2026-11-19T08:00:00Z';
    const targetDate = parseUtcDate(scheduledStartIso);

    const diffMs = targetDate.getTime() - now.getTime();
    const diffSec = Math.floor(diffMs / 1000);

    expect(diffSec).toBe(15 * 60); // 15 minutes = 900 seconds
  });

  it('handles countdown reaching zero and passing', () => {
    // Farm clock set past scheduled time
    useClockStore.getState().sync({
      mode: 'sim',
      speed: 1.0,
      paused: true,
      farm_now: '2026-11-19T08:05:00Z',
    });

    const now = computeFarmNow();
    const scheduledStartIso = '2026-11-19T08:00:00Z';
    const targetDate = parseUtcDate(scheduledStartIso);

    const diffMs = targetDate.getTime() - now.getTime();
    const countdownSec = Math.max(0, Math.floor(diffMs / 1000));

    expect(countdownSec).toBe(0);
  });
});
