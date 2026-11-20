import { useEffect, useState } from 'react';

export function useElapsedSeconds(isActive: boolean): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isActive) return;

    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);

    return () => {
      clearInterval(interval);
    };
  }, [isActive]);

  return isActive ? elapsed : 0;
}
