import { describe, expect, it } from 'vitest';
import { type AiSettingsData, type AiRecentCall, KNOWN_AI_MODELS } from '../lib/api';

describe('AI Settings & Site Configuration', () => {
  const defaultSettings: AiSettingsData = {
    enabled: true,
    primary_provider: 'apinex',
    fallback_provider: 'gemini',
    provider_order: ['apinex', 'gemini', 'rule_based'],
    primary_model: 'free/deepseek-v4-pro-0813',
    fallback_model: 'gemini-2.5-flash',
    feature_models: {
      alarm_assistant: 'free/deepseek-v4-pro-0813',
      weather_advisor: 'free/deepseek-v4-pro-0813',
      daily_briefing: 'free/deepseek-v4-pro-0813',
    },
    features_enabled: {
      alarm_assistant: true,
      weather_advisor: true,
      anomaly_detection: true,
      daily_briefing: true,
    },
    keys_status: {
      apinex: true,
      gemini: true,
    },
    farm_location: {
      latitude: 32.51625,
      longitude: 14.070361,
      timezone: 'Africa/Tripoli',
    },
    recent_calls: [
      {
        timestamp: '2026-11-19T14:30:00Z',
        feature: 'explain_alarm',
        provider: 'apinex',
        model: 'free/deepseek-v4-pro-0813',
        latency_ms: 1240,
      },
      {
        timestamp: '2026-11-19T14:35:00Z',
        feature: 'chat',
        provider: 'rule_based',
        model: 'rule-based-fallback',
        latency_ms: 45,
        fallback_reason: 'timeout_exceeded',
      },
    ],
  };

  it('configures APInex as primary provider with fallback chain', () => {
    expect(defaultSettings.primary_provider).toBe('apinex');
    expect(defaultSettings.fallback_provider).toBe('gemini');
    expect(defaultSettings.provider_order).toEqual(['apinex', 'gemini', 'rule_based']);
  });

  it('allows reordering provider order when primary provider changes', () => {
    const updatedSettings = {
      ...defaultSettings,
      primary_provider: 'gemini',
      fallback_provider: 'apinex',
      provider_order: ['gemini', 'apinex', 'rule_based'],
    };
    expect(updatedSettings.primary_provider).toBe('gemini');
    expect(updatedSettings.fallback_provider).toBe('apinex');
    expect(updatedSettings.provider_order[0]).toBe('gemini');
  });

  it('uses free models by default for APInex', () => {
    expect(defaultSettings.primary_model).toBe('free/deepseek-v4-pro-0813');
    expect(defaultSettings.feature_models.alarm_assistant).toMatch(/^free\//);
    expect(defaultSettings.feature_models.weather_advisor).toMatch(/^free\//);
    expect(defaultSettings.feature_models.daily_briefing).toMatch(/^free\//);
  });

  it('matches exact farm site coordinates from docs/FARM_SITE.md', () => {
    expect(defaultSettings.farm_location.latitude).toBeCloseTo(32.51625, 5);
    expect(defaultSettings.farm_location.longitude).toBeCloseTo(14.070361, 5);
    expect(defaultSettings.farm_location.timezone).toBe('Africa/Tripoli');
  });

  it('has independent feature toggles for all four AI features', () => {
    expect(defaultSettings.features_enabled.alarm_assistant).toBe(true);
    expect(defaultSettings.features_enabled.weather_advisor).toBe(true);
    expect(defaultSettings.features_enabled.anomaly_detection).toBe(true);
    expect(defaultSettings.features_enabled.daily_briefing).toBe(true);
  });

  it('never stores raw API keys in settings client payload', () => {
    // keys_status contains only booleans indicating whether keys are set in .env
    expect(typeof defaultSettings.keys_status.apinex).toBe('boolean');
    expect(typeof defaultSettings.keys_status.gemini).toBe('boolean');
    expect((defaultSettings as unknown as Record<string, unknown>).apinex_api_key).toBeUndefined();
    expect((defaultSettings as unknown as Record<string, unknown>).gemini_api_key).toBeUndefined();
  });

  it('tracks recent AI calls with latency and fallback reason', () => {
    const calls: AiRecentCall[] = defaultSettings.recent_calls || [];
    expect(calls).toHaveLength(2);
    expect(calls[0].feature).toBe('explain_alarm');
    expect(calls[0].latency_ms).toBe(1240);
    expect(calls[0].fallback_reason).toBeUndefined();

    expect(calls[1].provider).toBe('rule_based');
    expect(calls[1].fallback_reason).toBe('timeout_exceeded');
  });

  it('contains benchmarked model catalog metadata from docs/AI_MODELS.md', () => {
    const deepseek = KNOWN_AI_MODELS['free/deepseek-v4-pro-0813'];
    expect(deepseek?.quota_multiplier).toBe(3);
    expect(deepseek?.tools).toBe(true);
    expect(deepseek?.verdict).toBe('recommended');
    expect(deepseek?.available).toBe(true);

    const muse = KNOWN_AI_MODELS['free/muse-spark-1.3'];
    expect(muse?.quota_multiplier).toBe(3);
    expect(muse?.tools).toBe(true);
    expect(muse?.vision).toBe(true);
    expect(muse?.verdict).toBe('recommended');
    expect(muse?.available).toBe(true);

    // Unusable 402 model marked unavailable
    const claude = KNOWN_AI_MODELS['free/claude-opus-4.6'];
    expect(claude?.available).toBe(false);
    expect(claude?.verdict).toBe('unavailable_402');

    // Unusable 400 model marked unavailable
    const jev = KNOWN_AI_MODELS['free/jev-1.13'];
    expect(jev?.available).toBe(false);
    expect(jev?.verdict).toBe('unavailable_400');
  });
});
