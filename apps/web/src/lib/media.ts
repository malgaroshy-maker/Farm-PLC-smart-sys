/** Media-query hook (G4): render a component once for the current layout instead of mounting both. */
import { useSyncExternalStore } from 'react';

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia?.(query);
      mq?.addEventListener('change', cb);
      return () => mq?.removeEventListener('change', cb);
    },
    () => window.matchMedia?.(query).matches ?? false,
    () => false,
  );
}

/** Tailwind `lg` breakpoint (1024px). */
export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)');
