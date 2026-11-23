/** One-shot loader with explicit status (G4): pages show loading / error+retry / empty instead of guessing. */
import { useCallback, useEffect, useState } from 'react';

export type LoadStatus = 'loading' | 'error' | 'ok';

export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    setStatus('loading');
    load()
      .then((d) => {
        if (!live) return;
        setData(d);
        setStatus('ok');
      })
      .catch(() => live && setStatus('error'));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, setData, status, reload };
}
