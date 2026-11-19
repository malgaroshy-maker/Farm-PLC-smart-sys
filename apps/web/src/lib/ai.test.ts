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
  it('explainAlarm sends alarmId, language and AbortSignal to /api/v1/ai/explain-alarm', async () => {
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
      latency_ms: 320,
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockExplanation), { status: 200 }),
    );

    const controller = new AbortController();
    const res = await explainAlarm('alm_123', 'How to reset?', 'ar', controller.signal);
    expect(res).toMatchObject(mockExplanation);
    expect(res.latency_ms).toBe(320);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/v1/ai/explain-alarm');
    expect(init?.method).toBe('POST');
    expect(init?.signal).toBe(controller.signal);
    expect(JSON.parse(String(init?.body))).toMatchObject({
      alarm_id: 'alm_123',
      question: 'How to reset?',
      lang: 'ar',
    });
  });

  it('sendAiChat posts messages to /api/v1/ai/chat with latency and fallback_reason support', async () => {
    const mockChatRes = {
      message: 'Zone 1 and Zone 3 are currently running.',
      provider: 'APInex',
      model: 'free/gemini-3.8-flash',
      is_fallback: false,
      latency_ms: 850,
      fallback_reason: undefined,
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockChatRes), { status: 200 }),
    );

    const controller = new AbortController();
    const res = await sendAiChat([{ role: 'user', content: 'What is running?' }], 'en', controller.signal);
    expect(res).toMatchObject(mockChatRes);
    expect(res.latency_ms).toBe(850);

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/v1/ai/chat');
    expect(init?.signal).toBe(controller.signal);
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
      new Response(JSON.stringify({ ok: true, message: 'Suggestion approved' }), { status: 200 }),
    );

    const res = await approveSuggestion('sug_1');
    expect(res.ok).toBe(true);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/ai/suggestions/sug_1/approve');
  });

  it('rejectSuggestion posts reason to /api/v1/ai/suggestions/:id/reject', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, message: 'Suggestion rejected' }), { status: 200 }),
    );

    const res = await rejectSuggestion('sug_1', 'Operator override');
    expect(res.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/v1/ai/suggestions/sug_1/reject');
    expect(JSON.parse(String(init?.body))).toEqual({ reason: 'Operator override' });
  });

  it('fetchDailyBriefing fetches structured daily briefing', async () => {
    const mockBriefing = {
      date: '2026-11-20',
      morning_recap: 'All cycles completed normally yesterday.',
      water_used_yesterday_m3: 38.4,
      schedules_today: [{ program_name: 'Main Morning', start_time: '06:00', zones: ['Zone 1'] }],
      weather_forecast: { condition: 'sunny', temp_min_c: 19, temp_max_c: 31, rain_prob_pct: 0, precipitation_mm: 0 },
      provider: 'APInex',
      model: 'free/gemini-3.8-flash',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockBriefing), { status: 200 }),
    );

    const briefing = await fetchDailyBriefing('2026-11-20');
    expect(briefing.date).toBe('2026-11-20');
    expect(briefing.water_used_yesterday_m3).toBe(38.4);
    expect(briefing.weather_forecast.condition).toBe('sunny');
  });

  it('fetchAiSettings and updateAiSettings handle full configuration and recent calls', async () => {
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
      recent_calls: [
        {
          timestamp: '2026-11-19T14:30:00Z',
          feature: 'explain_alarm',
          provider: 'apinex',
          model: 'free/gemini-3.8-flash',
          latency_ms: 920,
        },
      ],
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(mockSettings), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...mockSettings, enabled: false }), { status: 200 }));

    const getRes = await fetchAiSettings();
    expect(getRes.enabled).toBe(true);
    expect(getRes.recent_calls).toHaveLength(1);
    expect(getRes.recent_calls?.[0].latency_ms).toBe(920);

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
