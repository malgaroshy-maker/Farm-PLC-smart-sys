import { describe, expect, it } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { useT } from './i18n';

describe('useT', () => {
  it('returns the same t function across renders (effects that depend on t must not re-run)', () => {
    const seen: unknown[] = [];
    function Probe({ n }: { n: number }) {
      const { t } = useT();
      seen.push(t);
      return createElement('span', null, n);
    }
    const root = createRoot(document.createElement('div'));
    act(() => root.render(createElement(Probe, { n: 1 })));
    act(() => root.render(createElement(Probe, { n: 2 })));
    act(() => root.unmount());
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(new Set(seen).size).toBe(1);
  });
});
