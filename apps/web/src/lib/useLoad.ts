/** One-shot loader with explicit status (G4): pages show loading / error+retry / empty instead of guessing. */
import { useCallback, useEffect, useState } from 'react';

export type LoadStatus = 'loading' | 'error' | 'ok';

interface Result<T> {
  key: string;
  data: T | null;
  status: Exclude<LoadStatus, 'loading'>;
}

export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [tick, setTick] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  // the request in flight; status is "loading" until a result for this exact key arrives
  const key = JSON.stringify([tick, ...deps]);

  useEffect(() => {
    let live = true;
    load()
      .then((data) => live && setResult({ key, data, status: 'ok' }))
      .catch(() => live && setResult((r) => ({ key, data: r?.data ?? null, status: 'error' })));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  const status: LoadStatus = result?.key === key ? result.status : 'loading';
  return { data: result?.data ?? null, status, reload };
}
