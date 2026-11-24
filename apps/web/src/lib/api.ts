/**
 * Thin fetch wrapper: base URL, bearer token, typed errors.
 *
 * By default the web app talks same-origin (`/api`, `/ws`) and the Vite dev
 * server proxies to the backend, so it also works from a phone on the LAN.
 * Set VITE_API_URL (e.g. http://192.168.1.20:8000) to call the API directly.
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
const TOKEN_KEY = 'farm.token';

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function wsUrl(token?: string): string {
  const base = API_BASE || window.location.origin;
  const url = new URL('/ws', base);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — session only */
  }
}

let token: string | null = readStorage(TOKEN_KEY);
const unauthorizedListeners = new Set<() => void>();

export const session = {
  get token() {
    return token;
  },
  set(value: string | null) {
    token = value;
    writeStorage(TOKEN_KEY, value);
  },
  onUnauthorized(fn: () => void) {
    unauthorizedListeners.add(fn);
    return () => unauthorizedListeners.delete(fn);
  },
};

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as { detail?: unknown; message?: unknown };
    if (typeof b.message === 'string') return b.message;
    if (typeof b.detail === 'string') return b.detail;
    if (Array.isArray(b.detail)) return 'Invalid request';
  }
  if (typeof body === 'string' && body.trim().length > 0 && body.length < 120) return body.trim();
  return `Request failed (${status})`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(apiUrl(path), { ...init, headers });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    if (res.status === 401 && token) {
      session.set(null);
      unauthorizedListeners.forEach((fn) => fn());
    }
    throw new ApiError(res.status, body, errorMessage(body, res.status));
  }
  return body as T;
}

// ─── Milestone E: AI API Types & Client ─────────────────────────────────

export interface AlarmExplanation {
  alarm_id?: string;
  summary: string;
  summary_ar?: string;
  likely_causes: string[];
  likely_causes_ar?: string[];
  steps: string[];
  steps_ar?: string[];
  safety_note: string;
  safety_note_ar?: string;
  confidence?: number;
  language?: string;
  provider?: string;
  model?: string;
  model_used?: string;
  is_fallback?: boolean;
  latency_ms?: number;
  fallback_reason?: string;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at?: string;
  provider?: string;
  model?: string;
  model_used?: string;
  is_fallback?: boolean;
  latency_ms?: number;
  fallback_reason?: string;
}

export interface ChatResponse {
  message: string;
  provider?: string;
  model?: string;
  model_used?: string;
  is_fallback?: boolean;
  latency_ms?: number;
  fallback_reason?: string;
}

export interface AdvisorSuggestion {
  id: string;
  program_id?: string;
  program_name?: string;
  program_name_ar?: string;
  zone_id?: string;
  action: 'skip' | 'shorten' | 'extend' | 'reschedule' | 'extra_run';
  adjustment_pct?: number;
  /** "why?" details (Milestone G2): the rule that fired and the inputs it used */
  rule?: string;
  inputs?: { key: string; value: number; unit: string }[];
  reason: string;
  reason_ar: string;
  weather_summary?: {
    condition: string;
    temperature_c?: number;
    rain_probability_pct?: number;
    precipitation_mm?: number;
    et0_mm?: number;
  };
  effective_date: string;
  status: 'pending' | 'approved' | 'rejected' | 'applied' | 'expired';
  provider?: string;
  model?: string;
  model_used?: string;
  is_fallback?: boolean;
  created_at: string;
  expires_at?: string;
}

export interface DailyBriefing {
  id?: string;
  date: string;
  morning_recap: string;
  morning_recap_ar?: string;
  water_used_yesterday_m3: number;
  schedules_today: Array<{
    program_id?: string;
    program_name: string;
    program_name_ar?: string;
    start_time: string;
    zones: string[];
    action?: string;
  }>;
  weather_forecast: {
    condition: string;
    temp_min_c: number;
    temp_max_c: number;
    rain_prob_pct: number;
    precipitation_mm: number;
    et0_mm?: number;
  };
  alarms_summary?: {
    active_count: number;
    anomalies_count?: number;
  };
  provider?: string;
  model?: string;
  model_used?: string;
  is_fallback?: boolean;
  generated_at: string;
}

export interface AiRecentCall {
  timestamp: string;
  feature: string;
  provider: string;
  model: string;
  latency_ms: number;
  fallback_reason?: string;
}

export interface AiSettingsData {
  enabled: boolean;
  primary_provider: string;
  fallback_provider: string;
  provider_order: string[];
  primary_model: string;
  fallback_model: string;
  feature_models: {
    alarm_assistant: string;
    weather_advisor: string;
    daily_briefing: string;
  };
  features_enabled: {
    alarm_assistant: boolean;
    weather_advisor: boolean;
    anomaly_detection: boolean;
    daily_briefing: boolean;
  };
  keys_status: {
    apinex: boolean;
    gemini: boolean;
  };
  farm_location: {
    latitude: number;
    longitude: number;
    timezone: string;
  };
  recent_calls?: AiRecentCall[];
}

export interface AiModelOption {
  id: string;
  name?: string;
  provider?: string;
  description?: string;
  is_free?: boolean;
  quota_multiplier?: number;
  tools?: boolean;
  vision?: boolean;
  verdict?: 'recommended' | 'warning' | 'avoid' | 'unavailable_402' | 'unavailable_400';
  verdict_label?: string;
  available?: boolean;
}

export interface AiTestResult {
  ok: boolean;
  provider: string;
  model: string;
  model_used?: string;
  latency_ms: number;
  error?: string;
}

export interface ZoneBaseline {
  zone_id: string;
  baseline_cycles_count: number;
  calibrated: boolean;
  is_calibrated?: boolean;
  runs_completed?: number;
  runs_required?: number;
  flow_median_m3h?: number;
  flow_mad_m3h?: number;
  flow_min_normal_m3h?: number;
  flow_max_normal_m3h?: number;
  pressure_median_bar?: number;
  pressure_mad_bar?: number;
  pressure_min_normal_bar?: number;
  pressure_max_normal_bar?: number;
  status?: 'normal' | 'high_flow_low_pressure' | 'low_flow_high_pressure' | 'insufficient_data';
  message?: string;
}

export async function explainAlarm(
  alarmId: string,
  question?: string,
  lang = 'ar',
  signal?: AbortSignal
): Promise<AlarmExplanation> {
  const startTime = performance.now();
  const raw = await apiFetch<Record<string, unknown>>('/api/v1/ai/explain-alarm', {
    method: 'POST',
    signal,
    body: JSON.stringify({
      alarm_id: alarmId,
      alarm_code: alarmId.startsWith('ALM-') ? alarmId : undefined,
      question,
      language: lang,
      lang,
    }),
  });
  const elapsed = Math.round(performance.now() - startTime);

  return {
    alarm_id: String(raw.alarm_id ?? raw.alarm_code ?? alarmId),
    summary: String(raw.summary ?? (lang === 'ar' ? raw.diagnosis_ar || raw.diagnosis : raw.diagnosis || raw.diagnosis_ar) ?? ''),
    summary_ar: raw.summary_ar ? String(raw.summary_ar) : raw.diagnosis_ar ? String(raw.diagnosis_ar) : '',
    likely_causes: Array.isArray(raw.likely_causes) ? (raw.likely_causes as string[]) : Array.isArray(raw.probable_causes) ? (raw.probable_causes as string[]) : [],
    likely_causes_ar: Array.isArray(raw.likely_causes_ar) ? (raw.likely_causes_ar as string[]) : Array.isArray(raw.probable_causes_ar) ? (raw.probable_causes_ar as string[]) : [],
    steps: Array.isArray(raw.steps) ? (raw.steps as string[]) : Array.isArray(raw.suggested_actions) ? (raw.suggested_actions as string[]) : [],
    steps_ar: Array.isArray(raw.steps_ar) ? (raw.steps_ar as string[]) : Array.isArray(raw.suggested_actions_ar) ? (raw.suggested_actions_ar as string[]) : [],
    safety_note: raw.safety_note ? String(raw.safety_note) : raw.safety_critical ? 'Critical PLC interlock active' : '',
    safety_note_ar: raw.safety_note_ar ? String(raw.safety_note_ar) : raw.safety_critical ? 'تنبيه سلامة: حماية PLC نشطة — لا تتجاوز قواطع الحماية' : '',
    confidence: typeof raw.confidence === 'number' ? raw.confidence : 0.95,
    language: raw.language ? String(raw.language) : lang,
    provider: raw.provider ? String(raw.provider) : raw.provider_used ? String(raw.provider_used) : 'APInex',
    model: raw.model ? String(raw.model) : raw.provider_used ? String(raw.provider_used) : 'free/deepseek-v4-pro-0813',
    model_used: raw.model_used ? String(raw.model_used) : raw.model ? String(raw.model) : undefined,
    is_fallback: Boolean(raw.is_fallback ?? (raw.provider_used === 'rule_based')),
    latency_ms: typeof raw.latency_ms === 'number' ? raw.latency_ms : typeof raw.latency === 'number' ? Math.round(raw.latency * 1000) : elapsed,
    fallback_reason: raw.fallback_reason ? String(raw.fallback_reason) : undefined,
  };
}

export async function sendAiChat(
  messages: Array<{ role: string; content: string }>,
  lang = 'ar',
  signal?: AbortSignal
): Promise<ChatResponse> {
  const startTime = performance.now();
  const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
  const history = messages.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));

  const raw = await apiFetch<Record<string, unknown>>('/api/v1/ai/chat', {
    method: 'POST',
    signal,
    body: JSON.stringify({
      message: lastUserMsg,
      language: lang,
      messages,
      lang,
      history,
    }),
  });
  const elapsed = Math.round(performance.now() - startTime);

  const replyText = String(raw.message ?? (lang === 'ar' ? raw.reply_ar || raw.reply : raw.reply || raw.reply_ar) ?? '');
  return {
    message: replyText,
    provider: raw.provider ? String(raw.provider) : raw.provider_used ? String(raw.provider_used) : 'APInex',
    model: raw.model ? String(raw.model) : raw.provider_used ? String(raw.provider_used) : 'free/deepseek-v4-pro-0813',
    model_used: raw.model_used ? String(raw.model_used) : raw.model ? String(raw.model) : undefined,
    is_fallback: Boolean(raw.is_fallback ?? (raw.provider_used === 'rule_based')),
    latency_ms: typeof raw.latency_ms === 'number' ? raw.latency_ms : typeof raw.latency === 'number' ? Math.round(raw.latency * 1000) : elapsed,
    fallback_reason: raw.fallback_reason ? String(raw.fallback_reason) : undefined,
  };
}

export async function fetchAiSuggestions(): Promise<AdvisorSuggestion[]> {
  const rawList = await apiFetch<Array<Record<string, unknown>>>('/api/v1/ai/suggestions');
  if (!Array.isArray(rawList)) return [];

  return rawList.map((s) => {
    const payload = (s.action_payload as Record<string, unknown>) ?? {};
    const factor = typeof payload.duration_factor === 'number' ? payload.duration_factor : 1.0;
    const adjustmentPct =
      factor === 0 ? -100 : Math.round((factor - 1.0) * 100);

    return {
      id: String(s.id),
      program_id: String(s.program_id ?? payload.program_id ?? 'prog_01'),
      program_name: String(s.title ?? s.program_name ?? 'Irrigation Program'),
      program_name_ar: String(s.title_ar ?? s.program_name_ar ?? s.title ?? 'برنامج الري'),
      zone_id: s.zone_id ? String(s.zone_id) : Array.isArray(payload.affected_zone_ids) ? String(payload.affected_zone_ids[0]) : undefined,
      action: ((a) => (a === 'reduce' ? 'shorten' : a))(
        s.action ?? payload.action ?? (factor === 0 ? 'skip' : factor < 1 ? 'shorten' : 'extend'),
      ) as AdvisorSuggestion['action'],
      rule: typeof payload.rule === 'string' ? payload.rule : undefined,
      inputs: Array.isArray(payload.inputs) ? (payload.inputs as AdvisorSuggestion['inputs']) : undefined,
      adjustment_pct: typeof s.adjustment_pct === 'number' ? s.adjustment_pct : adjustmentPct,
      // G7 soil suggestions carry their explanation in the description
      reason: String((payload.action === 'extra_run' ? s.description : s.reasoning) ?? s.description ?? s.reason ?? ''),
      reason_ar: String((payload.action === 'extra_run' ? s.description_ar : s.reasoning_ar) ?? s.description_ar ?? s.reason_ar ?? ''),
      weather_summary: (s.weather_summary ?? payload.weather_summary ?? {
        condition: 'partly_cloudy',
      }) as AdvisorSuggestion['weather_summary'],
      effective_date: String(s.effective_date ?? payload.target_date ?? (typeof s.created_at === 'string' ? s.created_at.slice(0, 10) : new Date().toISOString().slice(0, 10))),
      status: (s.status as AdvisorSuggestion['status']) ?? 'pending',
      provider: String(s.provider ?? s.provider_used ?? 'APInex'),
      model: String(s.model ?? 'free/deepseek-v4-pro-0813'),
      model_used: s.model_used ? String(s.model_used) : s.model ? String(s.model) : undefined,
      is_fallback: Boolean(s.is_fallback ?? (s.provider_used === 'rule_based')),
      created_at: String(s.created_at ?? new Date().toISOString()),
      expires_at: s.expires_at ? String(s.expires_at) : undefined,
    };
  });
}

export async function approveSuggestion(suggestionId: string): Promise<{ ok: boolean; message?: string }> {
  return apiFetch<{ ok: boolean; message?: string }>(`/api/v1/ai/suggestions/${suggestionId}/approve`, {
    method: 'POST',
  });
}

export async function rejectSuggestion(suggestionId: string, reason?: string): Promise<{ ok: boolean; message?: string }> {
  return apiFetch<{ ok: boolean; message?: string }>(`/api/v1/ai/suggestions/${suggestionId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function fetchDailyBriefing(date?: string): Promise<DailyBriefing> {
  const query = date ? `?date=${encodeURIComponent(date)}` : '';
  const raw = await apiFetch<Record<string, unknown>>(`/api/v1/ai/briefing${query}`);

  return {
    id: raw.id ? String(raw.id) : undefined,
    date: String(raw.date ?? new Date().toISOString().slice(0, 10)),
    morning_recap: String(raw.morning_recap ?? raw.summary ?? ''),
    morning_recap_ar: String(raw.morning_recap_ar ?? raw.summary_ar ?? ''),
    water_used_yesterday_m3: typeof raw.water_used_yesterday_m3 === 'number' ? raw.water_used_yesterday_m3 : 0,
    schedules_today: (raw.schedules_today as DailyBriefing['schedules_today']) ?? [],
    weather_forecast: (raw.weather_forecast as DailyBriefing['weather_forecast']) ?? {
      condition: 'sunny',
      temp_min_c: 18,
      temp_max_c: 28,
      rain_prob_pct: 0,
      precipitation_mm: 0,
    },
    alarms_summary: (raw.alarms_summary as DailyBriefing['alarms_summary']) ?? {
      active_count: 0,
    },
    provider: String(raw.provider ?? raw.provider_used ?? 'APInex'),
    model: String(raw.model ?? raw.provider_used ?? 'free/deepseek-v4-pro-0813'),
    model_used: raw.model_used ? String(raw.model_used) : raw.model ? String(raw.model) : undefined,
    is_fallback: Boolean(raw.is_fallback ?? (raw.provider_used === 'rule_based')),
    generated_at: String(raw.generated_at ?? raw.created_at ?? new Date().toISOString()),
  };
}

export async function fetchAiSettings(): Promise<AiSettingsData> {
  const raw = await apiFetch<Record<string, unknown>>('/api/v1/ai/settings');
  const weatherCoords = raw.weather_coordinates as { latitude?: number; longitude?: number } | undefined;

  return {
    enabled: typeof raw.enabled === 'boolean' ? raw.enabled : true,
    primary_provider: String(raw.primary_provider ?? 'apinex'),
    fallback_provider: String(raw.fallback_provider ?? 'gemini'),
    provider_order: Array.isArray(raw.provider_order) ? (raw.provider_order as string[]) : ['apinex', 'gemini', 'rule_based'],
    primary_model: String(raw.apinex_model ?? raw.primary_model ?? 'free/gemini-3.8-flash'),
    fallback_model: String(raw.gemini_model ?? raw.fallback_model ?? 'gemini-2.5-flash'),
    feature_models: (raw.feature_models as AiSettingsData['feature_models']) ?? {
      alarm_assistant: String(raw.apinex_model ?? 'free/gemini-3.8-flash'),
      weather_advisor: String(raw.apinex_model ?? 'free/gemini-3.8-flash'),
      daily_briefing: String(raw.apinex_model ?? 'free/gemini-3.8-flash'),
    },
    features_enabled: (raw.features_enabled as AiSettingsData['features_enabled']) ?? {
      alarm_assistant: true,
      weather_advisor: true,
      anomaly_detection: true,
      daily_briefing: true,
    },
    keys_status: (raw.keys_status as AiSettingsData['keys_status']) ?? {
      apinex: Boolean(raw.apinex_base_url),
      gemini: Boolean(raw.gemini_model),
    },
    farm_location: weatherCoords
      ? {
          latitude: weatherCoords.latitude ?? 32.51625,
          longitude: weatherCoords.longitude ?? 14.070361,
          timezone: String(raw.weather_timezone ?? 'Africa/Tripoli'),
        }
      : {
          latitude: 32.51625,
          longitude: 14.070361,
          timezone: 'Africa/Tripoli',
        },
    recent_calls: Array.isArray(raw.recent_calls)
      ? (raw.recent_calls as Record<string, unknown>[]).map((c) => ({
          timestamp: String(c.timestamp || c.created_at || new Date().toISOString()),
          feature: String(c.feature || 'chat'),
          provider: String(c.provider || c.provider_used || 'rule_based'),
          model: String(c.model || 'rule-based-fallback'),
          latency_ms:
            typeof c.latency_ms === 'number'
              ? c.latency_ms
              : typeof c.latency === 'number'
              ? Math.round(c.latency * 1000)
              : 0,
          fallback_reason: c.fallback_reason ? String(c.fallback_reason) : undefined,
        }))
      : [],
  };
}

export async function updateAiSettings(data: Partial<AiSettingsData>): Promise<AiSettingsData> {
  return apiFetch<AiSettingsData>('/api/v1/ai/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export const KNOWN_AI_MODELS: Record<string, Partial<AiModelOption>> = {
  'free/deepseek-v4-pro-0813': {
    name: 'DeepSeek V4 Pro (0813)',
    quota_multiplier: 3,
    tools: true,
    vision: false,
    verdict: 'recommended',
    verdict_label: 'Recommended default: fast & almost clean',
    available: true,
  },
  'free/muse-spark-1.3': {
    name: 'Muse Spark 1.3',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'recommended',
    verdict_label: 'Recommended second: cleanest Arabic',
    available: true,
  },
  'free/gemini-3.8-flash': {
    name: 'Gemini 3.8 Flash',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Fast; mixes in Korean and English words',
    available: true,
  },
  'free/hy4': {
    name: 'HY4',
    quota_multiplier: 2,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Cheaper; slow',
    available: true,
  },
  'free/hy4-flash': {
    name: 'HY4 Flash',
    quota_multiplier: 2,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Cheap and fast; noticeable mixing',
    available: true,
  },
  'free/deepseek-v4.1-flash': {
    name: 'DeepSeek V4.1 Flash',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Fast; mixing',
    available: true,
  },
  'free/qwen-3.8-max': {
    name: 'Qwen 3.8 Max',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'English words in Arabic',
    available: true,
  },
  'free/glm-5.3-flash': {
    name: 'GLM 5.3 Flash',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Mixing; large prompts',
    available: true,
  },
  'free/glm-5.3-flashx': {
    name: 'GLM 5.3 FlashX',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Mixing',
    available: true,
  },
  'free/minimax-m3.1-flash': {
    name: 'MiniMax M3.1 Flash',
    quota_multiplier: 2,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Slow',
    available: true,
  },
  'free/mimo-v2.6-pro': {
    name: 'MiMo V2.6 Pro',
    quota_multiplier: 2,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Slow and mixing',
    available: true,
  },
  'free/gemini-4-hydrogen': {
    name: 'Gemini 4 Hydrogen',
    quota_multiplier: 5,
    tools: true,
    vision: true,
    verdict: 'warning',
    verdict_label: 'Most expensive; mixing',
    available: true,
  },
  'free/gpt-6-luna': {
    name: 'GPT-6 Luna',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'avoid',
    verdict_label: 'Avoid: answered Arabic question in English',
    available: true,
  },
  'free/kimi-k3': {
    name: 'Kimi K3',
    quota_multiplier: 3,
    tools: true,
    vision: true,
    verdict: 'avoid',
    verdict_label: 'Avoid: heavy English/German mixing',
    available: true,
  },
  // Unusable 402 models
  'free/claude-opus-4.6': { name: 'Claude Opus 4.6', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/claude-sonnet-4.6': { name: 'Claude Sonnet 4.6', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/gemini-3.1-pro': { name: 'Gemini 3.1 Pro', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/glm-5.3': { name: 'GLM 5.3', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/kimi-k2.8': { name: 'Kimi K2.8', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/minimax-m3': { name: 'MiniMax M3', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/mimo-v2.6-flash': { name: 'MiMo V2.6 Flash', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  'free/deepseek-v4-flash-0731': { name: 'DeepSeek V4 Flash (0731)', verdict: 'unavailable_402', verdict_label: 'Subscription-only (HTTP 402)', available: false },
  // Unusable 400 models
  'free/jev-1.13': { name: 'JEV 1.13', verdict: 'unavailable_400', verdict_label: 'No chat support (HTTP 400)', available: false },
  // Direct Google Gemini
  'gemini-2.5-flash': { name: 'Google Gemini 2.5 Flash', quota_multiplier: 1, tools: true, vision: true, verdict: 'recommended', verdict_label: 'Fast direct Google model', available: true },
  'gemini-2.5-pro': { name: 'Google Gemini 2.5 Pro', quota_multiplier: 1, tools: true, vision: true, verdict: 'recommended', verdict_label: 'High reasoning direct Google model', available: true },
};

type ModelItem = string | { id: string; name?: string; provider?: string; is_free?: boolean; quota_multiplier?: number; tools?: boolean; vision?: boolean; verdict?: string; verdict_label?: string; available?: boolean };

export async function fetchAiModels(): Promise<AiModelOption[]> {
  const raw = await apiFetch<{ models?: ModelItem[] } | ModelItem[]>('/api/v1/ai/models');
  const list = Array.isArray(raw) ? raw : Array.isArray(raw?.models) ? raw.models : [];

  return list.map((m: ModelItem) => {
    const id = typeof m === 'string' ? m : m.id;
    const known = KNOWN_AI_MODELS[id] || {};
    const obj: Partial<AiModelOption> = typeof m === 'object' && m !== null ? (m as Partial<AiModelOption>) : {};

    const isUnavailable =
      obj.available === false ||
      known.available === false ||
      id.includes('claude') ||
      id === 'free/jev-1.13' ||
      id === 'free/gemini-3.1-pro' ||
      id === 'free/glm-5.3' ||
      id === 'free/kimi-k2.8' ||
      id === 'free/minimax-m3' ||
      id === 'free/mimo-v2.6-flash' ||
      id === 'free/deepseek-v4-flash-0731';

    return {
      id,
      name: String(obj.name || known.name || id),
      provider: String(obj.provider || known.provider || (id.includes('/') ? id.split('/')[0] : 'APInex')),
      is_free: typeof obj.is_free === 'boolean' ? obj.is_free : id.startsWith('free/'),
      quota_multiplier: typeof obj.quota_multiplier === 'number' ? obj.quota_multiplier : (known.quota_multiplier ?? (id.includes('hydrogen') ? 5 : id.includes('hy4') || id.includes('minimax') || id.includes('mimo') ? 2 : 3)),
      tools: typeof obj.tools === 'boolean' ? obj.tools : (known.tools ?? (id !== 'free/jev-1.13')),
      vision: typeof obj.vision === 'boolean' ? obj.vision : (known.vision ?? (id !== 'free/deepseek-v4-pro-0813' && id !== 'free/jev-1.13')),
      verdict: (obj.verdict as AiModelOption['verdict']) ?? known.verdict ?? (isUnavailable ? 'unavailable_402' : 'warning'),
      verdict_label: String(obj.verdict_label || known.verdict_label || ''),
      available: isUnavailable ? false : (typeof obj.available === 'boolean' ? obj.available : (known.available ?? true)),
    };
  });
}

export async function testAiConnection(provider?: string, model?: string): Promise<AiTestResult> {
  const raw = await apiFetch<Record<string, unknown>>('/api/v1/ai/test', {
    method: 'POST',
    body: JSON.stringify({ provider, model }),
  });

  return {
    ok: Boolean(raw.ok),
    provider: String(raw.provider ?? provider ?? 'APInex'),
    model: String(raw.model ?? model ?? 'free/deepseek-v4-pro-0813'),
    model_used: raw.model_used ? String(raw.model_used) : undefined,
    latency_ms: typeof raw.latency_ms === 'number' ? raw.latency_ms : typeof raw.latency === 'number' ? Math.round(raw.latency * 1000) : 0,
    error: raw.error ? String(raw.error) : undefined,
  };
}

export async function fetchZoneBaseline(zoneId: string): Promise<ZoneBaseline> {
  const raw = await apiFetch<Record<string, unknown>>(`/api/v1/ai/baselines/${zoneId}`);
  const isCalibrated = Boolean(raw.calibrated ?? raw.is_calibrated);

  return {
    zone_id: String(raw.zone_id ?? zoneId),
    baseline_cycles_count:
      typeof raw.baseline_cycles_count === 'number'
        ? raw.baseline_cycles_count
        : typeof raw.runs_completed === 'number'
        ? raw.runs_completed
        : 0,
    calibrated: isCalibrated,
    is_calibrated: isCalibrated,
    runs_completed:
      typeof raw.runs_completed === 'number'
        ? raw.runs_completed
        : typeof raw.baseline_cycles_count === 'number'
        ? raw.baseline_cycles_count
        : 0,
    runs_required: typeof raw.runs_required === 'number' ? raw.runs_required : 5,
    flow_median_m3h: typeof raw.flow_median_m3h === 'number' ? raw.flow_median_m3h : undefined,
    flow_mad_m3h: typeof raw.flow_mad_m3h === 'number' ? raw.flow_mad_m3h : undefined,
    flow_min_normal_m3h: typeof raw.flow_min_normal_m3h === 'number' ? raw.flow_min_normal_m3h : undefined,
    flow_max_normal_m3h: typeof raw.flow_max_normal_m3h === 'number' ? raw.flow_max_normal_m3h : undefined,
    pressure_median_bar: typeof raw.pressure_median_bar === 'number' ? raw.pressure_median_bar : undefined,
    pressure_mad_bar: typeof raw.pressure_mad_bar === 'number' ? raw.pressure_mad_bar : undefined,
    pressure_min_normal_bar: typeof raw.pressure_min_normal_bar === 'number' ? raw.pressure_min_normal_bar : undefined,
    pressure_max_normal_bar: typeof raw.pressure_max_normal_bar === 'number' ? raw.pressure_max_normal_bar : undefined,
    status: (raw.status as ZoneBaseline['status']) ?? (isCalibrated ? 'normal' : 'insufficient_data'),
    message: raw.message ? String(raw.message) : undefined,
  };
}

// ─── Weather Types & Client (Milestone F) ──────────────────────────────

export interface WeatherData {
  timestamp: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  wind_direction?: string | number;
  wind_direction_10m?: number;
  precipitation_mm?: number;
  precipitation_probability_pct?: number;
  cloud_cover_pct?: number;
  uv_index?: number;
  et0_mm?: number;
  condition?: string;
  description?: string;
  description_ar?: string;
}

export interface WeatherDaySummary {
  date: string;
  temp_min_c: number;
  temp_max_c: number;
  humidity_avg_pct?: number;
  precipitation_total_mm?: number;
  precipitation_probability_pct?: number;
  et0_mm?: number;
  condition?: string;
  description?: string;
  description_ar?: string;
}

export interface WeatherForecast {
  current: WeatherData;
  hourly: WeatherData[];
  daily: WeatherDaySummary[];
  last_fetched_at?: string;
  source?: string;
  cached?: boolean;
}

export async function fetchCurrentWeather(): Promise<WeatherData> {
  return apiFetch<WeatherData>('/api/v1/ai/weather/current');
}

export async function fetchWeatherForecast(forceRefresh = false): Promise<WeatherForecast> {
  const query = forceRefresh ? '?force_refresh=true' : '';
  return apiFetch<WeatherForecast>(`/api/v1/ai/weather/forecast${query}`);
}

// ── system health (Milestone G1) ─────────────────────────────────────────

export const SYSTEM_HEALTH_PATH = '/api/v1/system/health';
export type HealthStatus = 'ok' | 'warn' | 'fail';
export const HEALTH_COLOR: Record<HealthStatus, string> = { ok: '#00e5ff', warn: '#ffb300', fail: '#ff5449' };
export interface HealthCheck {
  key: 'database' | 'controller' | 'scheduler' | 'ai' | 'weather' | 'disk';
  status: HealthStatus;
  code: string;
  detail: Record<string, string | number | null>;
}
export interface SystemHealth {
  status: HealthStatus;
  version: string;
  uptime_sec: number;
  checked_at: string;
  checks: HealthCheck[];
}

// ── AI usage (Milestone G2) ──────────────────────────────────────────────

export interface AiUsageRow {
  name: string;
  calls: number;
  fallbacks: number;
  rule_based: number;
  avg_ms: number;
  p95_ms: number;
  requests: number;
  input_tokens: number;
  output_tokens: number;
}
export interface AiUsage {
  days: number;
  total: AiUsageRow;
  by_feature: AiUsageRow[];
  by_model: AiUsageRow[];
  fallback_reasons: Record<string, number>;
}

export function fetchAiUsage(days: number): Promise<AiUsage> {
  return apiFetch<AiUsage>(`/api/v1/ai/usage?days=${days}`);
}
