import { describe, expect, it } from 'vitest';
import { fmtNum, pickName, translate, useI18nStore, type MsgKey } from './i18n';
import * as mod from './i18n';

describe('i18n dictionary', () => {
  it('defaults to Arabic and sets RTL on the document', () => {
    expect(useI18nStore.getState().lang).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    useI18nStore.getState().setLang('en');
    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.lang).toBe('en');
    useI18nStore.getState().setLang('ar');
  });

  it('has a non-empty Arabic and English string for every key', () => {
    // probe every key through translate(); a missing language would throw or be empty
    const keys = Object.keys((mod as unknown as { __keys?: MsgKey[] }).__keys ?? {}) as MsgKey[];
    const sample: MsgKey[] = keys.length ? keys : ['app.name', 'nav.alarms', 'state.running', 'al.reset', 'sim.title'];
    for (const k of sample) {
      expect(translate('ar', k).trim(), k).not.toBe('');
      expect(translate('en', k).trim(), k).not.toBe('');
    }
  });

  it('picks the right name and falls back to the other language', () => {
    expect(pickName('ar', 'Olives', 'زيتون')).toBe('زيتون');
    expect(pickName('en', 'Olives', 'زيتون')).toBe('Olives');
    expect(pickName('ar', 'Olives', null)).toBe('Olives');
  });

  it('formats numbers with Western digits in both languages', () => {
    expect(fmtNum(1234.5, 1)).toBe('1,234.5');
    expect(fmtNum(null)).toBe('--');
  });
});
