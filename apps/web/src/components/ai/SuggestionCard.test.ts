import { describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { translate, type MsgKey } from '../../lib/i18n';
import type { AdvisorSuggestion } from '../../lib/api';

vi.mock('../../lib/auth', () => ({ useAuth: () => ({ can: () => true }) }));

// every rule / input the server can send (apps/api/app/services/ai/advisor_rules.py)
const RULES = ['rain_skip', 'rain_but_dry_reduce', 'heat_extend', 'heat_dry_extend', 'cool_moist_reduce'];
const INPUTS = ['rain_mm', 'rain_pct', 'temp_max_c', 'et0_mm', 'moisture_avg_pct', 'moisture_min_pct', 'water_48h_m3', 'zones_count'];

describe('advisor "why?"', () => {
  it('has Arabic and English text for every rule and input', () => {
    for (const k of [...RULES.map((r) => `advisor.rule.${r}`), ...INPUTS.map((i) => `advisor.input.${i}`)]) {
      expect(translate('ar', k as MsgKey), k).not.toBe(k);
      expect(translate('en', k as MsgKey), k).not.toBe(k);
    }
  });

  it('opens to show the rule and the real inputs', async () => {
    const { default: SuggestionCard } = await import('./SuggestionCard');
    const s: AdvisorSuggestion = {
      id: 'sug_1',
      action: 'skip',
      adjustment_pct: -100,
      reason: 'Rain expected',
      reason_ar: 'أمطار متوقعة',
      rule: 'rain_skip',
      inputs: [
        { key: 'rain_mm', value: 8, unit: 'mm' },
        { key: 'rain_pct', value: 85, unit: '%' },
      ],
      effective_date: '2026-11-24',
      status: 'pending',
    } as AdvisorSuggestion;
    const el = document.createElement('div');
    const root = createRoot(el);
    act(() => root.render(createElement(SuggestionCard, { suggestion: s })));
    expect(el.querySelector('[data-testid="advisor-why-details"]')).toBeNull();
    act(() => (el.querySelector('[data-testid="advisor-why"]') as HTMLButtonElement).click());
    const details = el.querySelector('[data-testid="advisor-why-details"]')!;
    expect(details.textContent).toContain(translate('ar', 'advisor.rule.rain_skip' as MsgKey));
    expect(details.textContent).toContain('85 %');
    act(() => root.unmount());
  });
});
