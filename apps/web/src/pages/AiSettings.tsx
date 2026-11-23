import { useEffect, useState } from 'react';
import AiUsagePanel from '../components/ai/AiUsagePanel';
import {
  Bot,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Key,
  MapPin,
  Zap,
  Activity,
  Layers,
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
  type AiRecentCall,
} from '../lib/api';
import { AiSparklesIcon } from '../components/icons/FarmIcons';

const DEFAULT_SETTINGS: AiSettingsData = {
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
  recent_calls: [],
};

export default function AiSettingsPage() {
  const { can } = useAuth();
  const { t } = useT();
  const isAdmin = can('owner_admin');

  const [settings, setSettings] = useState<AiSettingsData>(DEFAULT_SETTINGS);
  const [models, setModels] = useState<AiModelOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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

  const handlePrimaryProviderChange = (newPrimary: string) => {
    const fallback = newPrimary === 'apinex' ? 'gemini' : 'apinex';
    const newOrder = [newPrimary, fallback, 'rule_based'].filter((v, i, a) => a.indexOf(v) === i);
    setSettings({
      ...settings,
      primary_provider: newPrimary,
      fallback_provider: fallback,
      provider_order: newOrder,
    });
  };

  const handleFallbackProviderChange = (newFallback: string) => {
    const newOrder = [settings.primary_provider, newFallback, 'rule_based'].filter(
      (v, i, a) => a.indexOf(v) === i
    );
    setSettings({
      ...settings,
      fallback_provider: newFallback,
      provider_order: newOrder,
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    setSaveError(null);

    try {
      const updated = await updateAiSettings(settings);
      setSettings(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Save failed');
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
    } catch (err: unknown) {
      const elapsed = Math.round(performance.now() - startTime);
      setTestResult({
        ok: false,
        provider: settings.primary_provider,
        model: settings.primary_model,
        latency_ms: elapsed,
        error: err instanceof Error ? err.message : t('aiSettings.testFailed'),
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

  const recentCalls: AiRecentCall[] = settings.recent_calls || [];

  const renderModelOption = (m: AiModelOption) => {
    const verdictBadge =
      m.verdict === 'recommended'
        ? '✓'
        : m.verdict === 'warning'
        ? '⚠'
        : m.verdict === 'unavailable_402'
        ? '⛔ 402'
        : m.verdict === 'unavailable_400'
        ? '⛔ 400'
        : '⛔';

    const mult = m.quota_multiplier ? `×${m.quota_multiplier}` : '';
    const tools = m.tools ? '🛠' : '';
    const vision = m.vision ? '👁' : '';
    const flags = [mult, tools, vision].filter(Boolean).join(' ');
    const label = `${m.name || m.id}${flags ? ` [${flags}]` : ''} ${verdictBadge}${m.available === false ? ' (Unavailable)' : ''}`;

    return (
      <option
        key={m.id}
        value={m.id}
        disabled={m.available === false}
        className={m.available === false ? 'text-[#849396] bg-[#141416]' : 'text-[#e5e2e1] bg-[#141416]'}
      >
        {label}
      </option>
    );
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
          {saveError && (
            <span className="text-xs font-bold text-[#ff5449] flex items-center gap-1.5 animate-fadeIn">
              <AlertTriangle size={16} />
              {saveError}
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

        {/* Card 2: Provider Chain & Fallback (Editable) */}
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
            {/* Primary Provider Selector */}
            <div className="p-3 rounded-xl bg-black/30 border border-[#00e5ff]/30 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#00e5ff] text-black font-bold font-mono text-[11px] flex items-center justify-center">
                    1
                  </span>
                  <span className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.primaryProvider')}</span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/20">
                  {t('aiSettings.primary')}
                </span>
              </div>
              <select aria-label={t('aiSettings.primaryProvider')}
                value={settings.primary_provider}
                onChange={(e) => handlePrimaryProviderChange(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                <option value="apinex" className="bg-[#141416]">APInex Gateway (https://api.apinex.bond/v1)</option>
                <option value="gemini" className="bg-[#141416]">Google Gemini API (Direct)</option>
              </select>
            </div>

            {/* Fallback Provider Selector */}
            <div className="p-3 rounded-xl bg-black/30 border border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-white/15 text-[#e5e2e1] font-bold font-mono text-[11px] flex items-center justify-center">
                    2
                  </span>
                  <span className="text-xs font-bold text-[#e5e2e1]">{t('aiSettings.fallbackProvider')}</span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/5 text-[#849396]">
                  {t('aiSettings.fallback')}
                </span>
              </div>
              <select aria-label={t('aiSettings.fallbackProvider')}
                value={settings.fallback_provider}
                onChange={(e) => handleFallbackProviderChange(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                <option value="gemini" className="bg-[#141416]">Google Gemini API (Direct)</option>
                <option value="apinex" className="bg-[#141416]">APInex Gateway (https://api.apinex.bond/v1)</option>
                <option value="rule_based" className="bg-[#141416]">{t('aiSettings.ruleBasedOption')}</option>
              </select>
            </div>

            {/* Step 3: Rule-based Fallback (Always Active) */}
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
                {t('aiSettings.alwaysOn')}
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

            {testResult && testResult.ok && (
              <div className="p-3 rounded-xl bg-black/40 border border-[#7ee787]/30 flex items-center justify-between text-xs animate-fadeIn">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-[#7ee787]" />
                  <span className="font-bold text-[#e5e2e1]">{t('aiSettings.testSuccess')}</span>
                  <span className="text-[11px] text-[#849396]">({testResult.model_used || testResult.model})</span>
                </div>
                <div className="font-mono text-[#00e5ff] font-bold">
                  {testResult.latency_ms} ms
                </div>
              </div>
            )}

            {testResult && !testResult.ok && (
              <div className="p-3 rounded-xl bg-[#ff5449]/10 border border-[#ff5449]/30 flex items-center justify-between text-xs animate-fadeIn text-[#ffb4ab]">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={16} className="text-[#ff5449] shrink-0" />
                  <div className="min-w-0">
                    <div className="font-bold">{t('aiSettings.testFailed')}</div>
                    <div className="text-[11px] text-[#ffb4ab]/80 truncate">{testResult.error}</div>
                  </div>
                </div>
                <div className="font-mono text-[11px] text-[#849396] shrink-0">
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
            {/* Primary Default Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.modelUsed')} (Primary Gateway)
              </label>
              <select aria-label={t('aiSettings.modelUsed')}
                value={settings.primary_model}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    primary_model: e.target.value,
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map(renderModelOption)}
              </select>
            </div>

            {/* Alarm Assistant Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureAlarmAssistant')}
              </label>
              <select aria-label={t('aiSettings.featureAlarmAssistant')}
                value={settings.feature_models.alarm_assistant}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, alarm_assistant: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map(renderModelOption)}
              </select>
            </div>

            {/* Weather Advisor Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureAdvisor')}
              </label>
              <select aria-label={t('aiSettings.featureAdvisor')}
                value={settings.feature_models.weather_advisor}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, weather_advisor: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map(renderModelOption)}
              </select>
            </div>

            {/* Daily Briefing Model */}
            <div className="space-y-1.5">
              <label className="text-[#bac9cc] font-medium block">
                {t('aiSettings.featureBriefing')}
              </label>
              <select aria-label={t('aiSettings.featureBriefing')}
                value={settings.feature_models.daily_briefing}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    feature_models: { ...settings.feature_models, daily_briefing: e.target.value },
                  })
                }
                className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff]"
              >
                {models.map(renderModelOption)}
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
                <div className="font-bold text-[#e5e2e1]">APInex — {t('aiSettings.apiKey')}</div>
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
                <div className="font-bold text-[#e5e2e1]">Google Gemini — {t('aiSettings.apiKey')}</div>
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
                <span>{t('aiSettings.latitude')}:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.latitude}</span>
              </div>
              <div className="flex justify-between">
                <span>{t('aiSettings.longitude')}:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.longitude}</span>
              </div>
              <div className="flex justify-between">
                <span>{t('aiSettings.timezone')}:</span>
                <span className="text-[#e5e2e1]">{settings.farm_location.timezone}</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Model Catalog & Evaluation Summary Table */}
      <section className="panel p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <Layers className="text-[#00e5ff]" size={18} />
            <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.modelCatalog')}</h2>
          </div>
          <span className="text-[11px] text-[#849396] font-mono">
            {models.filter((m) => m.available).length} Active / {models.length} Total
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-start text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-[#849396] text-[11px]">
                <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.model')}</th>
                <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.multiplier')}</th>
                <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.tools')}</th>
                <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.vision')}</th>
                <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.verdict')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {models.map((m) => {
                const isAvail = m.available !== false;
                const verdictClass =
                  m.verdict === 'recommended'
                    ? 'bg-[#7ee787]/15 text-[#7ee787] border-[#7ee787]/30'
                    : m.verdict === 'warning'
                    ? 'bg-[#ffeb3b]/15 text-[#ffeb3b] border-[#ffeb3b]/30'
                    : 'bg-[#ff5449]/15 text-[#ffb4ab] border-[#ff5449]/30';

                return (
                  <tr key={m.id} className={`hover:bg-white/[0.02] transition-colors ${!isAvail ? 'opacity-50' : ''}`}>
                    <td className="py-2.5 px-3">
                      <div className="font-bold text-[#e5e2e1]">{m.name || m.id}</div>
                      <div className="font-mono text-[11px] text-[#849396]">{m.id}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#bac9cc] whitespace-nowrap">
                      ×{m.quota_multiplier || 1}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] whitespace-nowrap">
                      {m.tools ? <span className="text-[#7ee787]">✓</span> : <span className="text-[#849396]">—</span>}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] whitespace-nowrap">
                      {m.vision ? <span className="text-[#7ee787]">✓</span> : <span className="text-[#849396]">—</span>}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium border ${verdictClass}`}>
                        {m.verdict_label || m.verdict || 'Available'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <AiUsagePanel />

      {/* Recent AI Calls (Last 20) Table */}
      <section className="panel p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <Activity className="text-[#00e5ff]" size={18} />
            <h2 className="text-sm font-bold text-[#e5e2e1]">{t('aiSettings.recentCalls')}</h2>
          </div>
          <span className="text-[11px] font-mono text-[#849396] px-2 py-0.5 rounded bg-white/5">
            {recentCalls.length} / 20
          </span>
        </div>

        {recentCalls.length === 0 ? (
          <div className="py-8 text-center text-xs text-[#849396]">
            {t('aiSettings.noRecentCalls')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-[#849396] text-[11px]">
                  <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.time')}</th>
                  <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.feature')}</th>
                  <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.provider')}</th>
                  <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.model')}</th>
                  <th className="py-2.5 px-3 text-start font-medium">{t('ai.latency')}</th>
                  <th className="py-2.5 px-3 text-start font-medium">{t('aiSettings.fallbackReasonCol')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recentCalls.map((call, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#bac9cc] whitespace-nowrap">
                      {call.timestamp.replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-white/5 text-[#e5e2e1] border border-white/10">
                        {call.feature}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                          call.provider === 'rule_based'
                            ? 'bg-[#ff9f43]/15 text-[#ff9f43] border border-[#ff9f43]/30'
                            : 'bg-[#00e5ff]/15 text-[#00e5ff] border border-[#00e5ff]/30'
                        }`}
                      >
                        {call.provider}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#bac9cc] whitespace-nowrap">
                      {call.model}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#00e5ff] whitespace-nowrap">
                      {call.latency_ms >= 1000
                        ? `${(call.latency_ms / 1000).toFixed(1)} s`
                        : `${call.latency_ms} ms`}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {call.fallback_reason ? (
                        <span className="px-2 py-0.5 rounded text-[11px] bg-[#ff9f43]/15 text-[#ff9f43] border border-[#ff9f43]/30 font-medium">
                          {call.fallback_reason}
                        </span>
                      ) : (
                        <span className="text-[#849396]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
