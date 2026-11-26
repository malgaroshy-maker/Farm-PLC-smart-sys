import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import { sendAiChat } from '../../lib/api';
import { translate, useI18nStore } from '../../lib/i18n';
import FloatingAssistant from './FloatingAssistant';

vi.mock('../../lib/api', () => ({ sendAiChat: vi.fn() }));

describe('assistant evidence', () => {
  it.each(['ar', 'en'] as const)('shows only recognized sources and sends the question as entered in %s', async (lang) => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const previousLang = useI18nStore.getState().lang;
    useI18nStore.getState().setLang(lang);
    const prompt = translate(lang, 'chat.quickPrompt.waterYesterday');
    const sourceLine = `${translate(lang, 'chat.sources')} · ${translate(lang, 'chat.source.cycles')}`;
    const reply = lang === 'ar' ? 'بيانات الاختبار متاحة.' : 'Test records are available.';
    vi.mocked(sendAiChat).mockClear().mockResolvedValue({
      message: reply,
      provider: 'rule_based',
      model: 'farm_records',
      references: ['get_cycles', 'unknown_test_reference', 'get_cycles'],
    });

    try {
      act(() => root.render(createElement(FloatingAssistant)));
      act(() => container.querySelector('button')?.click());
      expect(container.textContent).not.toContain(sourceLine);
      expect(container.textContent).toContain('-- bar');
      const button = Array.from(container.querySelectorAll('button')).find((element) => element.textContent === prompt);
      expect(button).toBeDefined();
      await act(async () => button?.click());

      expect(sendAiChat).toHaveBeenCalledWith(
        [expect.objectContaining({ role: 'user', content: prompt })], lang, expect.any(AbortSignal),
      );
      const sources = Array.from(container.querySelectorAll('p')).find((element) => element.textContent === sourceLine);
      expect(sources?.previousElementSibling?.textContent).toBe(reply);
      expect(sources?.nextElementSibling?.querySelector('[data-testid="model-badge-fallback"]')).toBeNull();
      expect(container.textContent).not.toContain('unknown_test_reference');
    } finally {
      act(() => root.unmount());
      useI18nStore.getState().setLang(previousLang);
    }
  });
});
