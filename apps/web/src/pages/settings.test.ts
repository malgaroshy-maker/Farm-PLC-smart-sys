import { describe, expect, it } from 'vitest';
import { translate, type MsgKey } from '../lib/i18n';

// every switch the API exposes (apps/api/app/services/features.py)
const FEATURES = [
  'ai.chat', 'ai.alarm_explain', 'ai.advisor', 'ai.briefing',
  'map.weather_overlay', 'map.farm_life', 'map.irrigation_animation',
  'automation.scheduler', 'automation.advisor_auto', 'automation.anomaly', 'automation.soil',
  'notify.in_app', 'notify.telegram', 'notify.web_push',
];

describe('settings text', () => {
  it('every feature switch has an Arabic and English name and description', () => {
    for (const f of FEATURES) {
      for (const k of [`feature.${f}`, `feature.${f}.desc`]) {
        expect(translate('ar', k as MsgKey), k).not.toBe(k);
        expect(translate('en', k as MsgKey), k).not.toBe(k);
      }
    }
  });

  it('notification errors from the API are explained', () => {
    for (const code of ['telegram_token_missing', 'telegram_no_message']) {
      expect(translate('ar', `notify.err.${code}` as MsgKey)).not.toBe(`notify.err.${code}`);
    }
  });
});
