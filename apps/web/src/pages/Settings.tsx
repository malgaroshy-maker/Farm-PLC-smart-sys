/**
 * Settings (Milestone G3, owner's choice: one page with tabs).
 * Features · Notifications · Zones & equipment · AI. Admin only.
 */
import { lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Bell, Bot, LayoutGrid, ToggleRight } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { useT, type MsgKey } from '../lib/i18n';
import FeaturesTab from '../components/settings/FeaturesTab';
import NotificationsTab from '../components/settings/NotificationsTab';
import ZonesTab from '../components/settings/ZonesTab';

const AiSettingsPage = lazy(() => import('./AiSettings'));

const TABS = [
  { key: 'features', icon: ToggleRight, label: 'settings.tab.features' },
  { key: 'notifications', icon: Bell, label: 'settings.tab.notifications' },
  { key: 'zones', icon: LayoutGrid, label: 'settings.tab.zones' },
  { key: 'ai', icon: Bot, label: 'settings.tab.ai' },
] as const;

export default function SettingsPage() {
  const { t } = useT();
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((x) => x.key === params.get('tab'))?.key ?? 'features') as (typeof TABS)[number]['key'];

  if (!can('owner_admin')) {
    return <div className="panel p-6 text-sm text-[#bac9cc]">{t('settings.adminOnly')}</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t('settings.title')}</h1>
      <div role="tablist" className="flex gap-1 overflow-x-auto panel p-1 w-fit max-w-full">
        {TABS.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            data-testid={`settings-tab-${key}`}
            onClick={() => setParams({ tab: key })}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap ${
              tab === key ? 'bg-[#00e5ff]/15 text-[#00e5ff] font-bold' : 'text-[#849396] hover:text-[#e5e2e1]'
            }`}
          >
            <Icon size={16} />
            {t(label as MsgKey)}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === 'features' && <FeaturesTab />}
        {tab === 'notifications' && <NotificationsTab />}
        {tab === 'zones' && <ZonesTab />}
        {tab === 'ai' && (
          <Suspense fallback={<div className="text-sm text-[#849396]">{t('common.loading')}</div>}>
            <AiSettingsPage />
          </Suspense>
        )}
      </div>
    </div>
  );
}
