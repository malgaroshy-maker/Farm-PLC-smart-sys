import { useState, useEffect, useCallback } from 'react';

export interface ZoneLiveState {
  zone_id: string;
  state: string;
  health: string;
  source_mode?: string;
  pressure_bar?: number;
  flow_m3h?: number;
  moisture_pct?: number;
  runtime_sec: number;
  active_alarm_count: number;
  last_updated: string;
}

export interface PumpLiveState {
  pump_id: string;
  state: string;
  run_fb: boolean;
  fault: boolean;
  runtime_hours: number;
  last_updated: string;
}

export interface FarmMapState {
  system_mode: string;
  zones: ZoneLiveState[];
  pumps: PumpLiveState[];
  valves: any[];
  sensors: any[];
  tank_level_pct: number;
  main_pressure_bar: number;
  main_flow_m3h: number;
  active_alarms: any[];
  data_fresh: boolean;
  last_snapshot_ts: string;
}

export function useFarmConnector() {
  const [state, setState] = useState<FarmMapState | null>(null);
  const [connected, setConnected] = useState(false);

  // Poll full state map from backend
  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/v1/state/map');
        if (res.ok) {
          const data = await res.json();
          if (active) {
            setState(data);
            setConnected(data.data_fresh);
          }
        } else {
          if (active) setConnected(false);
        }
      } catch (err) {
        if (active) setConnected(false);
      }
      
      if (active) {
        setTimeout(poll, 1000);
      }
    };

    poll();

    return () => {
      active = false;
    };
  }, []);

  const sendCommand = useCallback(async (action: string, targetId: string) => {
    // Map UI actions to backend command_type values
    const commandTypeMap: Record<string, string> = {
      'start': 'start_zone',
      'stop': 'stop_zone',
    };
    const commandType = commandTypeMap[action] || action;

    try {
      const resp = await fetch('http://127.0.0.1:8000/api/v1/commands', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          command_type: commandType,
          target_type: 'zone',
          target_id: targetId,
          payload: {},
        })
      });
      return await resp.json();
    } catch (err) {
      console.error('Command failed', err);
      throw err;
    }
  }, []);

  return { state, connected, sendCommand };
}
