import { useEffect, useState } from 'react';
import { Navigate, NavLink, Outlet, Link } from 'react-router-dom';
import { Languages, LogOut, Menu, Sparkles, Volume2, VolumeX, X } from 'lucide-react';
import {
  AlarmIcon,
  EquipmentIcon,
  EventsIcon,
  MapIcon,
  ReportsIcon,
  ScheduleIcon,
  SimulatorIcon,
  StopAllIcon,
  ZonesIcon,
  AiSparklesIcon,
  type IconProps,
} from '../components/icons/FarmIcons';
import FloatingAssistant from '../components/ai/FloatingAssistant';
import InstallPrompt from '../components/InstallPrompt';
import { usePrefs } from '../lib/prefs';
import { useAuth } from '../lib/auth';
import { session } from '../lib/api';
import { useFarmStore } from '../store/farm';
import type { LinkStatus } from '../store/farm';
import { SEVERITY, topSeverity } from '../lib/alarms';
import { useI18nStore, useT, type MsgKey } from '../lib/i18n';
import { usePresenter } from '../lib/presenter';
import { useFarmClock } from '../lib/clock';
import SimTimeBadge from '../components/clock/SimTimeBadge';
import ClockHeaderChip from '../components/clock/ClockHeaderChip';
import { getBottomNavItems } from '../lib/nav';
import { usePoll } from '../lib/poll';
import { HEALTH_COLOR, SYSTEM_HEALTH_PATH, type SystemHealth } from '../lib/api';
import HealthPanel from '../components/HealthPanel';

const LINK: Record<LinkStatus, { key: MsgKey; color: string }> = {
  idle: { key: 'link.connecting', color: '#849396' },
  connecting: { key: 'link.connecting', color: '#ffeb3b' },
  live: { key: 'link.live', color: '#00e5ff' },
  polling: { key: 'link.polling', color: '#ffeb3b' },
  offline: { key: 'link.offline', color: '#ffb4ab' },
};

export default function DashboardLayout() {
  const { user, loading, logout, can } = useAuth();
  const { t, lang } = useT();
  const toggleLang = useI18nStore((s) => s.toggle);
  const presenter = usePresenter();
  const connect = useFarmStore((s) => s.connect);
  const disconnect = useFarmStore((s) => s.disconnect);
  const link = useFarmStore((s) => s.link);
  const fresh = useFarmStore((s) => s.state?.data_fresh ?? false);
  const alarms = useFarmStore((s) => s.state?.active_alarms);
  const sendCommand = useFarmStore((s) => s.sendCommand);
  const [stopMsg, setStopMsg] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const health = usePoll<SystemHealth>(user ? SYSTEM_HEALTH_PATH : null, 15000);
  const { formatted: clock } = useFarmClock(lang);
  const prefs = usePrefs();

  useEffect(() => {
    if (user && session.token) connect(session.token);
    return () => disconnect();
  }, [user, connect, disconnect]);

  if (loading) {
    return <div className="h-screen bg-[#0e0e0e] text-[#849396] flex items-center justify-center">{t('common.loading')}</div>;
  }
  if (!user) return <Navigate to="/login" replace />;

  const alarmCount = alarms?.length ?? 0;
  const worst = alarms ? topSeverity(alarms) : null;
  const isAdmin = can('owner_admin');
  const showTech = isAdmin && presenter.on;
  const linkStatus =
    (link === 'live' || link === 'polling') && !fresh ? { key: 'link.stale' as MsgKey, color: '#ffb4ab' } : LINK[link];
  // any failed / degraded health check turns the badge red / amber (owner 2026-11-23)
  const status =
    health && health.status !== 'ok' ? { key: linkStatus.key, color: HEALTH_COLOR[health.status] } : linkStatus;

  const handleStopAll = async () => {
    if (!window.confirm(t('header.stopAllConfirm'))) return;
    const res = await sendCommand({ command_type: 'stop_all', target_type: 'system' });
    setStopMsg(res.ok ? '✓' : res.message);
    setTimeout(() => setStopMsg(null), 4000);
  };

  const nav: { key: MsgKey; path: string; icon: (p: IconProps) => React.ReactNode; badge?: number }[] = [
    { key: 'nav.dashboard', path: '/', icon: MapIcon },
    { key: 'nav.zones', path: '/zones', icon: ZonesIcon },
    { key: 'nav.schedules', path: '/schedules', icon: ScheduleIcon },
    { key: 'nav.equipment', path: '/equipment', icon: EquipmentIcon },
    { key: 'nav.alarms', path: '/alarms', icon: AlarmIcon, badge: alarmCount },
    { key: 'nav.events', path: '/events', icon: EventsIcon },
    { key: 'nav.reports', path: '/reports', icon: ReportsIcon },
    ...(showTech ? [{ key: 'nav.simulator' as MsgKey, path: '/simulator', icon: SimulatorIcon }] : []),
    ...(isAdmin ? [{ key: 'nav.aiSettings' as MsgKey, path: '/settings/ai', icon: AiSparklesIcon }] : []),
  ];

  const bottomNav = getBottomNavItems(alarmCount);

  const sidebar = (
    <aside className="w-64 h-full border-e border-white/10 bg-[#141416]/90 backdrop-blur-xl flex flex-col">
      <div className="p-5 border-b border-[#353534] flex items-center gap-3">
        <img src="/map/logo.webp" alt="" className="w-10 h-10 object-contain" />
        <div className="min-w-0">
          <div className="text-lg font-bold text-[#e5e2e1] leading-tight">{t('app.name')}</div>
          <div className="text-xs text-[#849396]">{t('app.tagline')}</div>
        </div>
        <button className="ms-auto lg:hidden p-1 text-[#849396]" onClick={() => setMenuOpen(false)} aria-label="close menu">
          <X size={20} />
        </button>
      </div>
      <button
        type="button"
        onClick={() => setHealthOpen(true)}
        className="w-full px-5 py-2 flex items-center gap-2 border-b border-[#353534] hover:bg-white/5 cursor-pointer text-start"
        title={t('health.open')}
        aria-label={t('health.open')}
        data-testid="health-badge"
      >
        <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: status.color }} />
        <span className="text-xs font-bold" style={{ color: status.color }}>
          {t(status.key)}
        </span>
        {health && health.status !== 'ok' && (
          <span className="ms-auto text-[11px] font-bold" style={{ color: status.color }}>
            {t(`health.status.${health.status}` as MsgKey)}
          </span>
        )}
      </button>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {nav.map(({ key, path, icon: Icon, badge }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                isActive ? 'bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/30' : 'text-[#bac9cc] hover:bg-[#353534] hover:text-[#e5e2e1] border border-transparent'
              }`
            }
          >
            <Icon size={19} />
            <span className="font-medium">{t(key)}</span>
            {!!badge && (
              <span
                className="ms-auto min-w-6 px-1.5 py-0.5 rounded-full text-[11px] font-bold font-mono text-center text-[#0e0e0e]"
                style={{ backgroundColor: worst ? SEVERITY[worst].color : '#849396' }}
              >
                {badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-[#353534] space-y-1">
        {isAdmin && (
          <label className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm text-[#bac9cc] cursor-pointer hover:bg-[#353534]">
            <span>{t('nav.presenter')}</span>
            <input type="checkbox" checked={presenter.on} onChange={presenter.toggle} className="accent-[#00e5ff] w-4 h-4" />
          </label>
        )}
        <button onClick={toggleLang} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[#bac9cc] hover:bg-[#353534]">
          <Languages size={18} />
          <span>{t('common.lang')}</span>
        </button>
        <div className="px-3 pt-2 text-xs text-[#849396]">
          <div className="text-[#e5e2e1]">{user.name}</div>
          <div>{t(`role.${user.role}` as MsgKey)}</div>
        </div>
        <button onClick={logout} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[#849396] hover:bg-[#353534] hover:text-[#ffb4ab]">
          <LogOut size={18} />
          <span>{t('nav.logout')}</span>
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-dvh bg-[#0e0e0e] text-[#e5e2e1]">
      {/* desktop sidebar */}
      <div className="hidden lg:block shrink-0">{sidebar}</div>
      {/* mobile overlay sidebar */}
      {menuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <div className="relative">{sidebar}</div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <InstallPrompt />
        <header
          className="h-14 shrink-0 border-b border-white/10 bg-[#0e0e0e]/80 backdrop-blur-xl flex items-center gap-3 px-3 lg:px-6"
          style={{
            paddingTop: 'env(safe-area-inset-top, 0px)',
            paddingLeft: 'max(0.75rem, env(safe-area-inset-left, 0px))',
            paddingRight: 'max(0.75rem, env(safe-area-inset-right, 0px))',
          }}
        >
          <button className="lg:hidden p-2 text-[#bac9cc] min-h-[44px] min-w-[44px] flex items-center justify-center" onClick={() => setMenuOpen(true)} aria-label="menu">
            <Menu size={22} />
          </button>
          <img src="/map/logo.webp" alt="" className="w-7 h-7 lg:hidden" />
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs sm:text-sm text-[#849396] font-mono truncate" dir="ltr">
              {clock}
            </span>
            <SimTimeBadge />
            {showTech && <ClockHeaderChip />}
          </div>
          <div className="ms-auto flex items-center gap-3 sm:gap-5">
            <button
              onClick={prefs.toggleMute}
              title={t(prefs.muted ? 'header.unmute' : 'header.mute')}
              aria-label={t(prefs.muted ? 'header.unmute' : 'header.mute')}
              aria-pressed={prefs.muted}
              className="p-1.5 rounded-lg text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1]"
            >
              {prefs.muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
            <button
              onClick={prefs.toggleMotion}
              title={t('header.reduceMotion')}
              aria-label={t('header.reduceMotion')}
              aria-pressed={prefs.reduceMotion}
              className={`p-1.5 rounded-lg hover:bg-white/10 ${prefs.reduceMotion ? 'text-[#ffeb3b]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}
            >
              <Sparkles size={18} className={prefs.reduceMotion ? 'opacity-50' : ''} />
            </button>
            {stopMsg && <span className="text-xs text-[#ffeb3b] max-w-40 truncate">{stopMsg}</span>}
            <Link
              to="/alarms"
              className={`hidden sm:flex items-center gap-2 ${worst === 'S3' ? 'animate-pulse' : ''}`}
              style={{ color: worst ? SEVERITY[worst].color : '#849396' }}
            >
              <AlarmIcon size={18} accent={worst ? SEVERITY[worst].color : '#849396'} />
              <span className="text-sm font-bold">
                <span className="font-mono">{alarmCount}</span> {t('header.alarms')}
              </span>
            </Link>
            {can('owner_admin', 'operator') && (
              <button
                onClick={handleStopAll}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#ffb4ab] text-[#ffb4ab] hover:bg-[#ffb4ab] hover:text-[#410002] text-xs font-bold whitespace-nowrap transition-colors"
              >
                <StopAllIcon size={16} /> {t('header.stopAll')}
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6 pb-[calc(5rem+env(safe-area-inset-bottom,0px))] lg:pb-6">
          <Outlet />
        </main>
        <FloatingAssistant />
        {healthOpen && <HealthPanel initial={health} onClose={() => setHealthOpen(false)} />}

        {/* mobile bottom navigation */}
        <nav
          aria-label={t('nav.bottomNav')}
          className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-[#141416]/95 backdrop-blur-xl border-t border-white/10 grid grid-cols-4"
          style={{
            paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom, 0px))',
          }}
        >
          {bottomNav.map(({ key, path, icon: Icon, badge }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/' || path === '/map'}
              aria-label={t(key)}
              className={({ isActive }) =>
                `min-h-[44px] min-w-[44px] py-1.5 flex flex-col items-center justify-center gap-1 text-[11px] relative transition-colors ${
                  isActive ? 'text-[#00e5ff] font-bold bg-[#00e5ff]/5' : 'text-[#849396] hover:text-[#e5e2e1]'
                }`
              }
            >
              <Icon size={20} />
              <span className="truncate max-w-full px-0.5">{t(key)}</span>
              {!!badge && (
                <span
                  className="absolute top-1 start-1/2 ms-2 min-w-5 px-1 rounded-full text-[10px] font-bold font-mono text-[#0e0e0e]"
                  style={{ backgroundColor: worst ? SEVERITY[worst].color : '#849396' }}
                >
                  {badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
