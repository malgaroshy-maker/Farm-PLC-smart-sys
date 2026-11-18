import { useCallback } from 'react';
import type { ZoneLiveState } from '@algaroshy/contracts';
import { useFarmStore } from '../store/farm';
import type { CommandOutcome } from '../store/farm';

export type { ZoneLiveState };

/** Live farm state + zone commands, backed by the shared store. */
export function useFarmConnector() {
  const state = useFarmStore((s) => s.state);
  const link = useFarmStore((s) => s.link);
  const send = useFarmStore((s) => s.sendCommand);

  const sendCommand = useCallback(
    (action: 'start' | 'stop', zoneId: string): Promise<CommandOutcome> =>
      send({
        command_type: action === 'start' ? 'start_zone' : 'stop_zone',
        target_type: 'zone',
        target_id: zoneId,
      }),
    [send],
  );

  const connected = (link === 'live' || link === 'polling') && !!state?.data_fresh;
  return { state, link, connected, sendCommand };
}
