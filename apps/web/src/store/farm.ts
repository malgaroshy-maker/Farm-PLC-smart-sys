/**
 * One shared live connection for the whole app.
 *
 * WebSocket first (server pushes `state.snapshot` and change events); if the
 * socket drops, poll /state/map every 2 s while reconnecting with backoff.
 */
import { create } from 'zustand';
import type {
  Alarm,
  Command,
  CommandRejection,
  CommandRequest,
  FarmMapState,
  RealtimeEvent,
  ScenarioRun,
} from '@algaroshy/contracts';
import { ApiError, apiFetch, wsUrl } from '../lib/api';
import { useClockStore } from '../lib/clock';
import { upsertAlarm } from '../lib/alarms';
import { usePrefs } from '../lib/prefs';
import { playAlarmChime } from '../lib/sound';

export type LinkStatus = 'idle' | 'connecting' | 'live' | 'polling' | 'offline';

export type CommandOutcome =
  | { ok: true; command: Command }
  | { ok: false; message: string; code?: string };

interface FarmStore {
  state: FarmMapState | null;
  link: LinkStatus;
  commands: Record<string, Command>;
  scenario: ScenarioRun | null;
  /** latest NEW major/critical alarm — the map flies to it */
  focus: { alarmId: string; zoneId: string | null; deviceId: string | null; at: number } | null;
  clearFocus: () => void;
  connect: (token: string) => void;
  disconnect: () => void;
  sendCommand: (req: CommandRequest) => Promise<CommandOutcome>;
  alarmAction: (alarmId: string, action: 'ack' | 'reset') => Promise<string | null>;
}

const POLL_MS = 2000;
const MAX_BACKOFF_MS = 15000;

let socket: WebSocket | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let backoff = 1000;
let wanted: string | null = null; // token we should be connected with
// alarm ids already known — only alarms raised after we connected chime / fly-to
const seenAlarms = new Set<string>();
let primed = false;

export const useFarmStore = create<FarmStore>((set, get) => {
  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  };

  const pollOnce = async () => {
    try {
      const state = await apiFetch<FarmMapState>('/api/v1/state/map');
      if (!primed) {
        state.active_alarms.forEach((al) => seenAlarms.add(al.id));
        primed = true;
      }
      set({ state, link: get().link === 'live' ? 'live' : 'polling' });
    } catch {
      set({ link: 'offline' });
    }
  };

  const startPolling = () => {
    if (pollTimer) return;
    void pollOnce();
    pollTimer = setInterval(pollOnce, POLL_MS);
  };

  const handleEvent = (evt: RealtimeEvent) => {
    switch (evt.type) {
      case 'state.snapshot': {
        const snap = evt.payload as FarmMapState;
        if (!primed) {
          snap.active_alarms.forEach((a) => seenAlarms.add(a.id));
          primed = true;
        }
        if (snap.farm_now) {
          useClockStore.getState().sync(snap);
        }
        set({ state: snap });
        break;
      }
      case 'clock.changed': {
        useClockStore.getState().sync(evt.payload as Record<string, unknown>);
        break;
      }
      case 'command.updated': {
        const cmd = evt.payload as Command;
        set({ commands: { ...get().commands, [cmd.id]: cmd } });
        break;
      }
      case 'alarm.active': {
        const a = evt.payload as Alarm;
        if (primed && !seenAlarms.has(a.id) && (a.severity === 'S2' || a.severity === 'S3') && a.condition_active) {
          if (!usePrefs.getState().muted) playAlarmChime(a.severity);
          set({ focus: { alarmId: a.id, zoneId: a.zone_id, deviceId: a.device_id, at: Date.now() } });
        }
        seenAlarms.add(a.id);
        const s = get().state;
        if (s) set({ state: { ...s, active_alarms: upsertAlarm(s.active_alarms, a) } });
        break;
      }
      case 'alarm.updated':
      case 'alarm.acknowledged':
      case 'alarm.cleared':
      case 'alarm.reset': {
        const s = get().state;
        if (s) set({ state: { ...s, active_alarms: upsertAlarm(s.active_alarms, evt.payload as Alarm) } });
        break;
      }
      case 'scenario.updated':
        set({ scenario: evt.payload as ScenarioRun });
        break;
      case 'telemetry.stale': {
        const s = get().state;
        if (s) set({ state: { ...s, data_fresh: false } });
        break;
      }
      default:
        // zone/pump/mode change events are folded into the snapshot that follows.
        break;
    }
  };

  const open = (token: string) => {
    if (get().link === 'idle') set({ link: 'connecting' });
    const ws = new WebSocket(wsUrl(token));
    socket = ws;

    ws.onopen = () => {
      backoff = 1000;
      stopPolling();
      set({ link: 'live' });
    };
    ws.onmessage = (msg) => {
      try {
        handleEvent(JSON.parse(msg.data) as RealtimeEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      if (socket === ws) socket = null;
      if (wanted !== token) return; // intentional disconnect
      startPolling();
      set({ link: get().link === 'offline' ? 'offline' : 'polling' });
      retryTimer = setTimeout(() => wanted && open(wanted), backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    };
  };

  return {
    state: null,
    link: 'idle',
    commands: {},
    scenario: null,
    focus: null,
    clearFocus: () => set({ focus: null }),

    connect(token) {
      if (wanted === token && socket) return;
      get().disconnect();
      wanted = token;
      void useClockStore.getState().fetchClock();
      open(token);
    },

    disconnect() {
      wanted = null;
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
      stopPolling();
      socket?.close();
      socket = null;
      primed = false;
      seenAlarms.clear();
      set({ link: 'idle', state: null, commands: {}, scenario: null, focus: null });
    },

    async alarmAction(alarmId, action) {
      try {
        const alarm = await apiFetch<Alarm>(`/api/v1/alarms/${alarmId}/${action}`, { method: 'POST' });
        const s = get().state;
        if (s) set({ state: { ...s, active_alarms: upsertAlarm(s.active_alarms, alarm) } });
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : 'Action failed';
      }
    },

    async sendCommand(req) {
      try {
        const command = await apiFetch<Command>('/api/v1/commands', {
          method: 'POST',
          body: JSON.stringify(req),
        });
        set({ commands: { ...get().commands, [command.id]: command } });
        return { ok: true, command };
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          const body = err.body as CommandRejection;
          return { ok: false, message: body.message, code: body.code };
        }
        return { ok: false, message: err instanceof Error ? err.message : 'Command failed' };
      }
    },
  };
});
