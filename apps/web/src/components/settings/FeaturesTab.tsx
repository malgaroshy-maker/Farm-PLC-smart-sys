/** Feature switches grouped like the owner chose: AI · Map effects · Automation · Notifications. */
import { useState } from 'react';
import { useFeaturesData } from '../../lib/features';
import { setFeature } from '../../lib/settingsApi';
import { useT, type MsgKey } from '../../lib/i18n';

const GROUPS = ['ai', 'map', 'automation', 'notify'] as const;

export function Switch({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 disabled:opacity-40 ${on ? 'bg-[#00e5ff]' : 'bg-white/15'}`}
    >
      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-[#0e0e0e] transition-all ${on ? 'start-[22px]' : 'start-0.5'}`} />
    </button>
  );
}

export default function FeaturesTab() {
  const { t } = useT();
  const data = useFeaturesData();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!data) return <div className="text-sm text-[#849396]">{t('common.loading')}</div>;

  const toggle = async (key: string, on: boolean) => {
    setBusy(key);
    setError(null);
    try {
      await setFeature(key, on);
    } catch {
      setError(t('settings.saveFailed'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="features-tab">
      {GROUPS.map((g) => (
        <section key={g} className="panel p-4 space-y-3">
          <h2 className="text-sm font-bold">{t(`feature.group.${g}` as MsgKey)}</h2>
          {Object.entries(data.groups)
            .filter(([, grp]) => grp === g)
            .map(([key]) => {
              const label = t(`feature.${key}` as MsgKey);
              return (
                <div key={key} className="flex items-start gap-3 justify-between">
                  <div className="min-w-0">
                    <div className="text-sm">{label}</div>
                    <div className="text-[11px] text-[#849396]">{t(`feature.${key}.desc` as MsgKey)}</div>
                  </div>
                  <Switch on={data.features[key]} onChange={(v) => toggle(key, v)} label={label} disabled={busy === key} />
                </div>
              );
            })}
        </section>
      ))}
      {error && <div className="text-xs text-[#ff5449] md:col-span-2">{error}</div>}
    </div>
  );
}
