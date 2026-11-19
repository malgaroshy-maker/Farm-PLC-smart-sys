import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  explainAlarm,
  sendAiChat,
  fetchAiSuggestions,
  approveSuggestion,
  rejectSuggestion,
  fetchDailyBriefing,
  fetchAiSettings,
  updateAiSettings,
  fetchAiModels,
  testAiConnection,
  fetchZoneBaseline,
  session,
} from './api';

afterEach(() => {
  vi.restoreAllMocks();
  session.set(null);
});

describe('AI API endpoints client', () => {
  it('explainAlarm sends alarmId and language to /api/v1/ai/explain-alarm', async () => {
    session.set('test-token');
    const mockExplanation = {
      alarm_id: 'alm_123',
      summary: 'High pressure spike detected',
      likely_causes: ['Main valve closed abruptly'],
      steps: ['Inspect discharge valve'],
      safety_note: 'Never bypass pressure safety valve',
      provider: 'APInex',
      model: 'free/gemini-3.8-flash',
      is_fallback: false,
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockExplanation), { status: 200 }),
    );

    const res = await explainAlarm('alm_123', 'How to reset?', 'ar');
    expect(res).toMatchObject(mockExplanation);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/v1/ai/explain-alarm');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toMatchObject({
      alarm_id: 'alm_123',
      question: 'How to reset?',
      lang: 'ar',
    });
  });

  it('sendAiChat posts messages to /api/v1/ai/chat', async () => {
    const mockChatRes = {
      message: 'Zone 1 and Zone 3 are currently running.',
      provider: 'APInex',
      model: 'free/gemini-3.8-flash',
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockChatRes), { status: 200 }),
    );

    const res = await sendAiChat([{ role: 'user', content: 'What is running?' }], 'en');
    expect(res).toMatchObject(mockChatRes);

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/v1/ai/chat');
    expect(JSON.parse(String(init?.body))).toMatchObject({
      message: 'What is running?',
      lang: 'en',
    });
  });

  it('fetchAiSuggestions retrieves pending advisor suggestions', async () => {
    const mockSuggestions = [
      {
        id: 'sug_1',
        program_id: 'prog_morning',
        action: 'skip',
        reason: 'Heavy rain forecasted',
        reason_ar: 'توقعات بأمطار غزيرة',
        effective_date: '2026-11-20',
        status: 'pending',
      },
    ];

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockSuggestions), { status: 200 }),
    );

    const res = await fetchAiSuggestions();
    expect(res).toHaveLength(1);
    expect(res[0]).toMatchObject(mockSuggestions[0]);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/ai/suggestions');
  });

  it('approveSuggestion posts to /api/v1/ai/suggestions/:id/approve', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, message: 'Applied override' }), { status: 200 }),
    );

    const res = await approveSuggestion('sug_1');
    expect(res.ok).toBe(true);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/ai/suggestions/sug_1/approve');
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST');
  });

  it('rejectSuggestion posts to /api/v1/ai/suggestions/:id/reject with reason', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    const res = await rejectSuggestion('sug_1', 'Soil is sandy, need irrigation anyway');
    expect(res.ok).toBe(true);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/ai/suggestions/sug_1/reject');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      reason: 'Soil is sandy, need irrigation anyway',
    });
  });

  it('fetchDailyBriefing supports date query parameter', async () => {
    const mockBriefing = {
      date: '2026-11-20',
      morning_recap: 'Stable irrigation yesterday',
      water_used_yesterday_m3: 38.2,
      schedules_today: [],
      weather_forecast: { condition: 'sunny', temp_min_c: 17, temp_max_c: 28, rain_prob_pct: 0, precipitation_mm: 0 },
      generated_at: '2026-11-20T06:00:00Z',
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockBriefing), { status: 200 }),
    );

    const res = await fetchDailyBriefing('2026-11-20');
    expect(res.water_used_yesterday_m3).toBe(38.2);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/ai/briefing?date=2026-11-20');
  });

  it('fetchAiSettings and updateAiSettings talk to /api/v1/ai/settings', async () => {
    const mockSettings = {
      enabled: true,
      primary_provider: 'apinex',
      fallback_provider: 'gemini',
      provider_order: ['apinex', 'gemini', 'rule_based'],
      primary_model: 'free/gemini-3.8-flash',
      fallback_model: 'gemini-2.5-flash',
      feature_models: {
        alarm_assistant: 'free/gemini-3.8-flash',
        weather_advisor: 'free/gemini-3.8-flash',
        daily_briefing: 'free/gemini-3.8-flash',
      },
      features_enabled: {
        alarm_assistant: true,
        weather_advisor: true,
        anomaly_detection: true,
        daily_briefing: true,
      },
      keys_status: { apinex: true, gemini: true },
      farm_location: { latitude: 32.51625, longitude: 14.070361, timezone: 'Africa/Tripoli' },
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(mockSettings), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...mockSettings, enabled: false }), { status: 200 }));

    const getRes = await fetchAiSettings();
    expect(getRes.enabled).toBe(true);

    const putRes = await updateAiSettings({ enabled: false });
    expect(putRes.enabled).toBe(false);
    expect(fetchMock.mock.calls[1][1]?.method).toBe('PUT');
  });

  it('fetchAiModels returns APInex model list', async () => {
    const mockModels = [
      { id: 'free/gemini-3.8-flash', name: 'Gemini 3.8 Flash', is_free: true },
      { id: 'free/gpt-4o-mini', name: 'GPT-4o Mini', is_free: true },
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockModels), { status: 200 }),
    );

    const list = await fetchAiModels();
    expect(list).toHaveLength(2);
    expect(list[0].id).toBe('free/gemini-3.8-flash');
  });

  it('testAiConnection measures latency and verifies model used', async () => {
    const mockTest = {
      ok: true,
      provider: 'apinex',
      model: 'free/gemini-3.8-flash',
      latency_ms: 184,
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockTest), { status: 200 }),
    );

    const result = await testAiConnection('apinex', 'free/gemini-3.8-flash');
    expect(result.ok).toBe(true);
    expect(result.latency_ms).toBe(184);
  });

  it('fetchZoneBaseline retrieves baseline statistics for a zone', async () => {
    const mockBaseline = {
      zone_id: 'zone_01',
      baseline_cycles_count: 7,
      is_calibrated: true,
      flow_median_m3h: 15.0,
      flow_mad_m3h: 0.9,
      flow_min_normal_m3h: 13.5,
      flow_max_normal_m3h: 16.5,
      pressure_median_bar: 2.5,
      pressure_mad_bar: 0.2,
      pressure_min_normal_bar: 2.2,
      pressure_max_normal_bar: 2.8,
      status: 'normal',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockBaseline), { status: 200 }),
    );

    const baseline = await fetchZoneBaseline('zone_01');
    expect(baseline.is_calibrated).toBe(true);
    expect(baseline.flow_median_m3h).toBe(15.0);
    expect(baseline.pressure_median_bar).toBe(2.5);
  });
});
