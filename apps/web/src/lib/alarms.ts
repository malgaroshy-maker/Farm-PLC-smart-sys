import type { Alarm, AlarmSeverity } from '@algaroshy/contracts';

/** ALARM_MATRIX.md §3 — S0 info · S1 warning · S2 major · S3 critical. */
export const SEVERITY: Record<AlarmSeverity, { label: string; labelAr: string; color: string; rank: number }> = {
  S3: { label: 'CRITICAL', labelAr: 'حرج', color: '#ff5449', rank: 3 },
  S2: { label: 'MAJOR', labelAr: 'كبير', color: '#ff9f43', rank: 2 },
  S1: { label: 'WARNING', labelAr: 'تحذير', color: '#ffeb3b', rank: 1 },
  S0: { label: 'INFO', labelAr: 'معلومة', color: '#4fc3f7', rank: 0 },
};

export function sortAlarms(alarms: Alarm[]): Alarm[] {
  return [...alarms].sort(
    (a, b) =>
      SEVERITY[b.severity].rank - SEVERITY[a.severity].rank ||
      b.triggered_at.localeCompare(a.triggered_at),
  );
}

export function topSeverity(alarms: Alarm[]): AlarmSeverity | null {
  return sortAlarms(alarms)[0]?.severity ?? null;
}

export function isOpen(alarm: Alarm): boolean {
  return alarm.status === 'active_unacked' || alarm.status === 'active_acked';
}

/** Fold a realtime alarm event into the open-alarm list. */
export function upsertAlarm(list: Alarm[], alarm: Alarm): Alarm[] {
  const rest = list.filter((a) => a.id !== alarm.id);
  return isOpen(alarm) ? sortAlarms([...rest, alarm]) : rest;
}

export type AlarmAction = 'ack' | 'reset';

/** Which operator actions make sense right now (permissions are checked separately). */
export function availableActions(alarm: Alarm): AlarmAction[] {
  const actions: AlarmAction[] = [];
  if (alarm.status === 'active_unacked') actions.push('ack');
  if (isOpen(alarm) && !alarm.condition_active && (alarm.requires_manual_reset || alarm.status === 'active_acked')) {
    actions.push('reset');
  }
  return actions;
}

export function describeState(alarm: Alarm): string {
  if (alarm.status === 'cleared') return 'CLEARED';
  const acked = alarm.status === 'active_acked' ? 'ACKED' : 'UNACKED';
  return alarm.condition_active ? `ACTIVE · ${acked}` : `LATCHED · ${acked}`;
}
