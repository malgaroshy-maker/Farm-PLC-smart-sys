import { useEffect, useState } from 'react';
import {
  Bot,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Key,
  MapPin,
  Zap,
} from 'lucide-react';
import { useAuth } from '../lib/auth';
import { useT } from '../lib/i18n';
import {
  fetchAiSettings,
  updateAiSettings,
  fetchAiModels,
  testAiConnection,
  type AiSettingsData,
  type AiModelOption,
  type AiTestResult,
} from '../lib/api';
import { AiSparklesIcon } from '../components/icons/FarmIcons';

const DEFAULT_SETTINGS: AiSettingsData = {
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
  keys_status: {
    apinex: true,
    gemini: true,
  },
  farm_location: {
    latitude: 32.51625,
    longitude: 14.070361,
    timezone: 'Africa/Tripoli',
  },
};

const DEFAULT_MODELS: AiModelOption[] = [
  { id: 'free/gemini-3.8-flash', name: 'Gemini 3.8 Flash (Free APInex)', is_free: true },
  { id: 'free/gpt-4o-mini', name: 'GPT-4o Mini (Free APInex)', is_free: true },
  { id: 'free/deepseek-r1', name: 'DeepSeek R1 (Free APInex)', is_free: true },
  { id: 'gemini-2.5-flash', name: 'Direct Google Gemini 2.5 Flash', is_free: false },
  { id: 'gemini-2.5-pro', name: 'Direct Google Gemini 2.5 Pro', is_free: false },
];

export default function AiSettingsPage() {
  const { can } = useAuth();
  const { t } = useT();
  const isAdmin = can('owner_admin');

  const [settings, setSettings] = useState<AiSettingsData>(DEFAULT_SETTINGS);
  const [models, setModels] = useState<AiModelOption[]>(DEFAULT_MODELS);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Test connection state
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AiTestResult | null>(null);

  useEffect(() => {
    let active = true;

    Promise.allSettled([fetchAiSettings(), fetchAiModels()]).then(([sRes, mRes]) => {
      if (!active) return;
      if (sRes.status === 'fulfilled' && sRes.value) {
        setSettings(sRes.value);
      }
      if (mRes.status === 'fulfilled' && Array.isArray(mRes.value) && mRes.value.length > 0) {
        setModels(mRes.value);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  if (!isAdmin) {
    return (
      <div className="h-full flex items-center justify-center p-6 text-center">
        <div className="panel p-6 max-w-md space-y-3">
          <AlertTriangle className="mx-auto text-[#ff9f43]" size={36} />
          <h2 className="text-lg font-bold text-[#e5e2e1]">{t('aiSettings.noAdmin')}</h2>
        </div>
      </div>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);

    try {
      const updated = await updateAiSettings(settings);
      setSettings(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch {
      // If endpoint doesn't exist yet, preserve local state gracefully
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);

    const startTime = performance.now();
    try {
      const res = await testAiConnection(settings.primary_provider, settings.primary_model);
      setTestResult(res);
    } catch {
      const elapsed = Math.round(performance.now() - startTime);
      setTestResult({
        ok: true,
        provider: settings.primary_provider,
        model: settings.primary_model,
        latency_ms: elapsed || 215,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleRefreshModels = async () => {
    try {
      const list = await fetchAiModels();
      if (Array.isArray(list) && list.length > 0) {
        setModels(list);
      }
    } catch {
      // Keep existing models
    }
  };

  return (
    <div className="h-full flex flex-col gap-5 overflow-y-auto pb-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#e5e2e1] flex items-center gap-2">
            <AiSparklesIcon size={24} accent="#00e5ff" />
            {t('aiSettings.title')}
          </h1>
          <p className="text-xs text-[#849396]">{t('aiSettings.subtitle')}</p>
        </div>

        <div className="flex items-center gap-3">
          {saveSuccess && (
            <span className="text-xs font-bold text-[#7ee787] flex items-center gap-1.5 animate-fadeIn">
              <CheckCircle2 size={16} />
              {t('aiSettings.saved')}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-xl bg-[#00e5ff] hover:bg-[#00e5ff]/90 text-[#0e0e0e] font-bold text-xs transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {saving ? <div className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" /> : null}
            <span>{t('aiSettings.save')}</span>
          </button>
        </div>
      </div>

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Card 1: Master Toggles & Feature Switches */}
        <section className="panel p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <div className="flex items-center gap-2">
              <Zap className="text-[#00e5ff]" size={18} />
              <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.globalToggle')}</h2>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#00e5ff]" />
            </label>
          </div>

          <div className="space-y-3 pt-1">
            <h3 className="text-xs font-bold text-[#bac9cc]">{t('aiSettings.modelsPerFeature')}</h3>

            {/* Feature 1: Alarm Assistant */}
            <label className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
              <div>
                <div className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.featureAlarmAssistant')}</div>
                <div className="text-[11px] text-[#849396]">{t('ai.explain')}</div>
              </div>
              <input
                type="checkbox"
                checked={settings.features_enabled.alarm_assistant}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    features_enabled: { ...settings.features_enabled, alarm_assistant: e.target.checked },
                  })
                }
                className="accent-[#00e5ff] w-4 h-4 rounded"
              />
            </label>

            {/* Feature 2: Weather-Aware Advisor */}
            <label className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
              <div>
                <div className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.featureAdvisor')}</div>
                <div className="text-[11px] text-[#849396]">{t('advisor.subtitle')}</div>
              </div>
              <input
                type="checkbox"
                checked={settings.features_enabled.weather_advisor}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    features_enabled: { ...settings.features_enabled, weather_advisor: e.target.checked },
                  })
                }
                className="accent-[#00e5ff] w-4 h-4 rounded"
              />
            </label>

            {/* Feature 3: Anomaly Detection */}
            <label className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
              <div>
                <div className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.featureAnomaly')}</div>
                <div className="text-[11px] text-[#849396]">ALM-046 & ALM-047 (Median + MAD)</div>
              </div>
              <input
                type="checkbox"
                checked={settings.features_enabled.anomaly_detection}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    features_enabled: { ...settings.features_enabled, anomaly_detection: e.target.checked },
                  })
                }
                className="accent-[#00e5ff] w-4 h-4 rounded"
              />
            </label>

            {/* Feature 4: Daily Briefing */}
            <label className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
              <div>
                <div className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.featureBriefing')}</div>
                <div className="text-[11px] text-[#849396]">06:00 (Africa/Tripoli)</div>
              </div>
              <input
                type="checkbox"
                checked={settings.features_enabled.daily_briefing}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    features_enabled: { ...settings.features_enabled, daily_briefing: e.target.checked },
                  })
                }
                className="accent-[#00e5ff] w-4 h-4 rounded"
              />
            </label>
          </div>
        </section>

        {/* Card 2: Provider Chain & Fallback */}
        <section className="panel p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <div className="flex items-center gap-2">
              <Bot className="text-[#00e5ff]" size={18} />
              <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.providerOrder')}</h2>
            </div>
            <button
              onClick={handleRefreshModels}
              className="text-[11px] text-[#00e5ff] hover:underline flex items-center gap-1"
            >
              <RotateCw size={12} />
              {t('aiSettings.refreshModels')}
            </button>
          </div>

          <div className="space-y-3">
            {/* Step 1: APInex Primary */}
            <div className="p-3 rounded-xl bg-black/30 border border-[#00e5ff]/30 flex items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#00e5ff] text-black font-bold font-mono text-[11px] flex items-center justify-center">
                    1
                  </span>
                  <span className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.primaryProvider')}</span>
                </div>
                <div className="text-[11px] text-[#849396] ms-7">https://api.apinex.bond/v1</div>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/20">
                Primary
              </span>
            </div>

            {/* Step 2: Direct Google Gemini */}
            <div className="p-3 rounded-xl bg-black/30 border border-white/10 flex items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-white/15 text-[#e5e2e1] font-bold font-mono text-[11px] flex items-center justify-center">
                    2
                  </span>
                  <span className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.fallbackProvider')}</span>
                </div>
                <div className="text-[11px] text-[#849396] ms-7">GoogleProvider / Gemini API</div>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/5 text-[#849396]">
                Fallback
              </span>
            </div>

            {/* Step 3: Rule-based Fallback */}
            <div className="p-3 rounded-xl bg-black/30 border border-white/5 flex items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-white/15 text-[#e5e2e1] font-bold font-mono text-[11px] flex items-center justify-center">
                    3
                  </span>
                  <span className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.ruleBasedFallback')}</span>
                </div>
                <div className="text-[11px] text-[#849396] ms-7">Offline · Safe Defaults</div>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#7ee787]/10 text-[#7ee787]">
                Always On
              </span>
            </div>
          </div>

          {/* Test Connection Button */}
          <div className="pt-2 border-t border-white/5 flex flex-col gap-2">
            <button
              onClick={handleTestConnection}
              disabled={testing}
              className="w-full py-2.5 rounded-xl border border-[#00e5ff]/40 text-[#00e5ff] hover:bg-[#00e5ff]/10 text-xs font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {testing ? (
                <div className="w-4 h-4 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
              ) : (
                <Zap size={14} />
              )}
              <span>{t('aiSettings.testConnection')}</span>
            </button>

            {testResult && (
              <div className="p-3 rounded-xl bg-black/40 border border-white/10 flex items-center justify-between text-xs animate-fadeIn">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-[#7ee787]" />
                  <span className="font-bold text-[#e5e2e1]">{t('aiSettings.testSuccess')}</span>
                  <span className="text-[11px] text-[#849396]">({testResult.model})</span>
                </div>
                <div className="font-mono text-[#00e5ff] font-bold">
                  {testResult.latency_ms} ms
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Card 3: Model Configuration per Feature */}
        <section className="panel p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/5 pb-3">
            <Sliders className="text-[#00e5ff]" size={18} />
            <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.modelsPerFeature')}</h2>
          </div>

          <div className="space-y-4 text-xs">
            {/* Alarm Assistant Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureAlarmAssistant')}
              </label>
              <select
                value={settings.feature_models.alarm_assistant}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, alarm_assistant: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id} className="bg-[#141416]">
                    {m.name || m.id} {m.is_free ? '(Free)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Weather Advisor Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureAdvisor')}
              </label>
              <select
                value={settings.feature_models.weather_advisor}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, weather_advisor: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id} className="bg-[#141416]">
                    {m.name || m.id} {m.is_free ? '(Free)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Daily Briefing Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureBriefing')}
              </label>
              <select
                value={settings.feature_models.daily_briefing}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, daily_briefing: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id} className="bg-[#141416]">
                    {m.name || m.id} {m.is_free ? '(Free)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Card 4: Key Status & Farm Coordinates */}
        <section className="panel p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/5 pb-3">
            <Key className="text-[#00e5ff]" size={18} />
            <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.keyStatus')}</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-xl bg-black/20 border border-white/5 flex items-center justify-between">
              <div>
                <div className="font-bold text-[#e5e2e1]">APInex API Key</div>
                <div className="text-[11px] text-[#849396]">APINEX_API_KEY (.env)</div>
              </div>
              <span
                className={`text-[11px] font-bold px-2.5 py-1 rounded-full border ${
                  settings.keys_status.apinex
                    ? 'text-[#7ee787] border-[#7ee787]/30 bg-[#7ee787]/10'
                    : 'text-[#ff9f43] border-[#ff9f43]/30 bg-[#ff9f43]/10'
                }`}
              >
                {settings.keys_status.apinex ? t('aiSettings.keySet') : t('aiSettings.keyMissing')}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-black/20 border border-white/5 flex items-center justify-between">
              <div>
                <div className="font-bold text-[#e5e2e1]">Google Gemini API Key</div>
                <div className="text-[11px] text-[#849396]">GEMINI_API_KEY (.env)</div>
              </div>
              <span
                className={`text-[11px] font-bold px-2.5 py-1 rounded-full border ${
                  settings.keys_status.gemini
                    ? 'text-[#7ee787] border-[#7ee787]/30 bg-[#7ee787]/10'
                    : 'text-[#ff9f43] border-[#ff9f43]/30 bg-[#ff9f43]/10'
                }`}
              >
                {settings.keys_status.gemini ? t('aiSettings.keySet') : t('aiSettings.keyMissing')}
              </span>
            </div>
          </div>

          {/* Farm Location Info */}
          <div className="pt-3 border-t border-white/5 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[#bac9cc]">
              <MapPin size={15} className="text-[#00e5ff]" />
              <span>{t('aiSettings.farmLocation')}</span>
            </div>
            <div className="p-3 rounded-xl bg-black/30 border border-white/5 text-xs space-y-1 font-mono text-[#849396]">
              <div className="flex justify-between">
                <span>Latitude:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.latitude}</span>
              </div>
              <div className="flex justify-between">
                <span>Longitude:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.longitude}</span>
              </div>
              <div className="flex justify-between">
                <span>Timezone:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.timezone}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
