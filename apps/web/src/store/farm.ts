/**
 * One shared live connection for the whole app.
 *
 * WebSocket first (server pushes `state.snapshot` and change events); if the
 * socket drops, poll /state/map every 2 s while reconnecting with backoff.
 */
import { create } from 'zustand';
import type {
  Command,
  CommandRejection,
  CommandRequest,
  FarmMapState,
  RealtimeEvent,
} from '@algaroshy/contracts';
import { ApiError, apiFetch, wsUrl } from '../lib/api';

export type LinkStatus = 'idle' | 'connecting' | 'live' | 'polling' | 'offline';

export type CommandOutcome =
  | { ok: true; command: Command }
  | { ok: false; message: string; code?: string };

interface FarmStore {
  state: FarmMapState | null;
  link: LinkStatus;
  commands: Record<string, Command>;
  connect: (token: string) => void;
  disconnect: () => void;
  sendCommand: (req: CommandRequest) => Promise<CommandOutcome>;
}

const POLL_MS = 2000;
const MAX_BACKOFF_MS = 15000;

let socket: WebSocket | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let backoff = 1000;
let wanted: string | null = null; // token we should be connected with

export const useFarmStore = create<FarmStore>((set, get) => {
  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  };

  const pollOnce = async () => {
    try {
      const state = await apiFetch<FarmMapState>('/api/v1/state/map');
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
      case 'state.snapshot':
        set({ state: evt.payload as FarmMapState });
        break;
      case 'command.updated': {
        const cmd = evt.payload as Command;
        set({ commands: { ...get().commands, [cmd.id]: cmd } });
        break;
      }
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

    connect(token) {
      if (wanted === token && socket) return;
      get().disconnect();
      wanted = token;
      open(token);
    },

    disconnect() {
      wanted = null;
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
      stopPolling();
      socket?.close();
      socket = null;
      set({ link: 'idle', state: null, commands: {} });
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
