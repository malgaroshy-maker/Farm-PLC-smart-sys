import { describe, expect, it, beforeEach } from 'vitest';
import {
  useClockStore,
  computeFarmNow,
  formatFarmClock,
  farmHourAndMonth,
  parseUtcDate,
} from './clock';

describe('virtual farm clock', () => {
  beforeEach(() => {
    useClockStore.setState({
      mode: 'real',
      speed: 1.0,
      paused: false,
      anchorSimMs: Date.parse('2026-11-19T05:30:00Z'),
      clientRecvMs: typeof performance !== 'undefined' ? performance.now() : Date.now(),
      isSimulated: false,
    });
  });

  it('syncs clock state from server data', () => {
    useClockStore.getState().sync({
      mode: 'sim',
      speed: 60,
      paused: false,
      farm_now: '2026-11-19T12:00:00',
    });

    const state = useClockStore.getState();
    expect(state.mode).toBe('sim');
    expect(state.speed).toBe(60);
    expect(state.paused).toBe(false);
    expect(state.isSimulated).toBe(true);
    expect(new Date(state.anchorSimMs).toISOString()).toBe('2026-11-19T12:00:00.000Z');

    // Test with +00:00 timezone offset (FastAPI output)
    useClockStore.getState().sync({
      farm_now: '2026-11-19T14:30:00+00:00',
    });
    expect(new Date(useClockStore.getState().anchorSimMs).toISOString()).toBe('2026-11-19T14:30:00.000Z');
  });

  it('detects isSimulated if paused or speed != 1', () => {
    useClockStore.getState().sync({
      mode: 'real',
      speed: 1.0,
      paused: true,
      farm_now: '2026-11-19T12:00:00Z',
    });
    expect(useClockStore.getState().isSimulated).toBe(true);

    useClockStore.getState().sync({
      mode: 'real',
      speed: 1.0,
      paused: false,
      farm_now: '2026-11-19T12:00:00Z',
    });
    expect(useClockStore.getState().isSimulated).toBe(false);
  });

  it('computeFarmNow respects paused state', () => {
    useClockStore.getState().sync({
      mode: 'sim',
      speed: 360,
      paused: true,
      farm_now: '2026-11-19T05:30:00Z',
    });

    const now1 = computeFarmNow();
    expect(now1.toISOString()).toBe('2026-11-19T05:30:00.000Z');
  });

  it('extracts hour and month in Tripoli timezone', () => {
    // 2026-11-19T03:30:00Z is 05:30 in Africa/Tripoli (UTC+2)
    const d = new Date('2026-11-19T03:30:00Z');
    const { hour, month } = farmHourAndMonth(d);
    expect(Math.floor(hour)).toBe(5);
    expect(Math.round((hour - 5) * 60)).toBe(30);
    expect(month).toBe(11);
  });

  it('formats clock string in Arabic and English', () => {
    const d = new Date('2026-11-19T03:30:00Z');
    const ar = formatFarmClock(d, 'ar');
    const en = formatFarmClock(d, 'en');

    expect(ar).toBeTruthy();
    expect(en).toContain('05:30:00');
  });

  it('parseUtcDate reliably parses naive and timezone-offset strings as UTC', () => {
    // String without timezone (e.g. from SQLite)
    const dNaive = parseUtcDate('2026-11-19T10:00:00');
    expect(dNaive.toISOString()).toBe('2026-11-19T10:00:00.000Z');

    // String with +00:00 (FastAPI format)
    const dOffset = parseUtcDate('2026-11-19T10:00:00+00:00');
    expect(dOffset.toISOString()).toBe('2026-11-19T10:00:00.000Z');

    // String with Z
    const dZ = parseUtcDate('2026-11-19T10:00:00Z');
    expect(dZ.toISOString()).toBe('2026-11-19T10:00:00.000Z');

    // Empty or null
    expect(parseUtcDate(null)).toBeInstanceOf(Date);
    expect(parseUtcDate('')).toBeInstanceOf(Date);
  });

  it('safely handles invalid dates in formatFarmClock and farmHourAndMonth', () => {
    const invalidDate = new Date('invalid');
    expect(formatFarmClock(invalidDate, 'ar')).toBe('—');
    const { hour, month } = farmHourAndMonth(invalidDate);
    expect(hour).toBe(12);
    expect(month).toBe(1);
  });
});
