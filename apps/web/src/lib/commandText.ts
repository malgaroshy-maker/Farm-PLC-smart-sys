/** Why a command was refused or did not finish, in the viewer's language. */
import { tr, type MsgKey } from './i18n';

const CODES = [
  'zone_disabled',
  'critical_alarm_active',
  'state_stale',
  'mode_blocks_start',
  'no_power',
  'zone_manual',
  'zone_already_active',
  'duplicate_command',
  'max_concurrent_zones',
  'combination_not_allowed',
  'no_pump_available',
  'tank_critically_low',
] as const;

export function rejectionText(code: string | undefined, serverMessage: string): string {
  return code && (CODES as readonly string[]).includes(code)
    ? tr(`reject.${code}` as MsgKey)
    : serverMessage;
}

/** The controller reports short codes (plc_no_ack, tank_low...) in failure_reason. */
export function failureText(reason: string | null | undefined): string {
  if (!reason) return tr('cmd.failed');
  const code = reason.split(':')[0].trim();
  const known: Record<string, MsgKey> = {
    plc_no_ack: 'fail.plc_no_ack',
    plc_rejected: 'fail.plc_rejected',
    interlock: 'fail.interlock',
    zone_in_manual: 'reject.zone_manual',
    no_power: 'reject.no_power',
    pump_unavailable: 'reject.no_pump_available',
    tank_low: 'reject.tank_critically_low',
    estop_active: 'fail.estop_active',
    already_running: 'reject.zone_already_active',
    bad_target: 'fail.bad_target',
  };
  return known[code] ? tr(known[code]) : `${tr('cmd.failed')}: ${reason}`;
}
