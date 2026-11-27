import { useEffect } from 'react';
import type { Command } from '@algaroshy/contracts';
import { useFarmStore } from '../store/farm';
import { apiFetch } from './api';

export const COMMAND_DONE = ['completed', 'failed', 'rejected', 'timed_out'];

/** The newest state of one command, asking the server while the live socket is down. */
export function useCommandResult(id: string | null): Command | null {
  const cmd = useFarmStore((s) => (id ? s.commands[id] : undefined));
  const link = useFarmStore((s) => s.link);
  useEffect(() => {
    if (!id || link === 'live' || (cmd && COMMAND_DONE.includes(cmd.status))) return;
    const timer = setInterval(async () => {
      try {
        const recent = await apiFetch<Command[]>('/api/v1/commands?limit=50');
        const found = recent.find((c) => c.id === id);
        if (found) useFarmStore.setState((s) => ({ commands: { ...s.commands, [id]: found } }));
      } catch {
        /* the offline banner already says so */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [id, link, cmd]);
  return cmd ?? null;
}
