import { describe, expect, it } from 'vitest';
import type { Alarm } from '@algaroshy/contracts';
import { availableActions, describeState, sortAlarms, topSeverity, upsertAlarm } from './alarms';

function alarm(over: Partial<Alarm>): Alarm {
  return {
    id: 'a1',
    alarm_code: 'ALM-005',
    name: 'Booster Pump Fault / Trip',
    name_ar: null,
    severity: 'S3',
    category: 'equipment',
    status: 'active_unacked',
    zone_id: null,
    device_type: 'pump',
    device_id: 'pump_booster_01',
    source_layer: 'plc',
    current_value: null,
    threshold_value: null,
    triggered_at: '2026-11-18T10:00:00Z',
    acknowledged_at: null,
    acknowledged_by: null,
    cleared_at: null,
    reset_at: null,
    reset_by: null,
    message_ar: null,
    message_en: null,
    guidance_ar: null,
    guidance_en: null,
    condition_active: true,
    requires_ack: true,
    requires_manual_reset: true,
    ...over,
  };
}

describe('severity ordering', () => {
  it('puts critical (S3) first and newest first within a level', () => {
    const list = [
      alarm({ id: 'info', severity: 'S0' }),
      alarm({ id: 'old-crit', triggered_at: '2026-11-18T09:00:00Z' }),
      alarm({ id: 'warn', severity: 'S1' }),
      alarm({ id: 'new-crit' }),
    ];
    expect(sortAlarms(list).map((a) => a.id)).toEqual(['new-crit', 'old-crit', 'warn', 'info']);
    expect(topSeverity(list)).toBe('S3');
    expect(topSeverity([])).toBeNull();
  });
});

describe('upsertAlarm', () => {
  it('adds, replaces and removes cleared alarms', () => {
    let list = upsertAlarm([], alarm({}));
    expect(list).toHaveLength(1);
    list = upsertAlarm(list, alarm({ status: 'active_acked' }));
    expect(list[0].status).toBe('active_acked');
    list = upsertAlarm(list, alarm({ status: 'cleared' }));
    expect(list).toEqual([]);
  });
});

describe('availableActions', () => {
  it('offers ack only while unacked', () => {
    expect(availableActions(alarm({}))).toEqual(['ack']);
  });

  it('does not offer reset while the condition is still active', () => {
    expect(availableActions(alarm({ status: 'active_acked' }))).toEqual([]);
  });

  it('offers reset for a latched alarm once the condition is gone', () => {
    const latched = alarm({ status: 'active_acked', condition_active: false });
    expect(availableActions(latched)).toEqual(['reset']);
    expect(describeState(latched)).toBe('LATCHED · ACKED');
  });

  it('offers reset for an alarm the controller holds, even while active', () => {
    const held = alarm({ status: 'active_acked', controller_reset: true });
    expect(availableActions(held)).toEqual(['reset']);
    expect(availableActions({ ...held, reset_at: '2026-11-24T10:00:00Z' })).toEqual([]);
  });

  it('offers nothing for history entries', () => {
    expect(availableActions(alarm({ status: 'cleared', condition_active: false }))).toEqual([]);
    expect(describeState(alarm({ status: 'cleared' }))).toBe('CLEARED');
  });
});
