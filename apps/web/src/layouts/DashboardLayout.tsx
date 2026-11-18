import { useEffect, useState } from 'react';
import { Navigate, NavLink, Outlet, Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Cpu,
  FlaskConical,
  Languages,
  LayoutGrid,
  LogOut,
  Menu,
  OctagonX,
  ScrollText,
  X,
} from 'lucide-react';
import { useAuth } from '../lib/auth';
import { session } from '../lib/api';
import { useFarmStore } from '../store/farm';
import type { LinkStatus } from '../store/farm';
import { SEVERITY, topSeverity } from '../lib/alarms';
import { useI18nStore, useT, type MsgKey } from '../lib/i18n';
import { usePresenter } from '../lib/presenter';

const LINK: Record<LinkStatus, { key: MsgKey; color: string }> = {
  idle: { key: 'link.connecting', color: '#849396' },
  connecting: { key: 'link.connecting', color: '#ffeb3b' },
  live: { key: 'link.live', color: '#00e5ff' },
  polling: { key: 'link.polling', color: '#ffeb3b' },
  offline: { key: 'link.offline', color: '#ffb4ab' },
};

/** Clock in farm local time (Africa/Tripoli). */
function useFarmClock(lang: string) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const fmt = new Intl.DateTimeFormat(lang === 'ar' ? 'ar-LY-u-nu-latn' : 'en-GB', {
    timeZone: 'Africa/Tripoli',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  });
  return fmt.format(now);
}

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
  const clock = useFarmClock(lang);

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
  const status =
    (link === 'live' || link === 'polling') && !fresh ? { key: 'link.stale' as MsgKey, color: '#ffb4ab' } : LINK[link];

  const handleStopAll = async () => {
    if (!window.confirm(t('header.stopAllConfirm'))) return;
    const res = await sendCommand({ command_type: 'stop_all', target_type: 'system' });
    setStopMsg(res.ok ? '✓' : res.message);
    setTimeout(() => setStopMsg(null), 4000);
  };

  const nav: { key: MsgKey; path: string; icon: typeof Activity; badge?: number }[] = [
    { key: 'nav.dashboard', path: '/', icon: Activity },
    { key: 'nav.zones', path: '/zones', icon: LayoutGrid },
    { key: 'nav.equipment', path: '/equipment', icon: Cpu },
    { key: 'nav.alarms', path: '/alarms', icon: AlertTriangle, badge: alarmCount },
    { key: 'nav.events', path: '/events', icon: ScrollText },
    ...(showTech ? [{ key: 'nav.simulator' as MsgKey, path: '/simulator', icon: FlaskConical }] : []),
  ];

  const sidebar = (
    <aside className="w-64 h-full border-e border-[#353534] bg-[#1c1b1b] flex flex-col">
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
      <div className="px-5 py-2 flex items-center gap-2 border-b border-[#353534]" title={link}>
        <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: status.color }} />
        <span className="text-xs font-bold" style={{ color: status.color }}>
          {t(status.key)}
        </span>
      </div>

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
        <header className="h-14 shrink-0 border-b border-[#353534] bg-[#0e0e0e] flex items-center gap-3 px-3 lg:px-6">
          <button className="lg:hidden p-2 text-[#bac9cc]" onClick={() => setMenuOpen(true)} aria-label="menu">
            <Menu size={22} />
          </button>
          <img src="/map/logo.webp" alt="" className="w-7 h-7 lg:hidden" />
          <span className="text-xs sm:text-sm text-[#849396] font-mono truncate" dir="ltr">
            {clock}
          </span>
          <div className="ms-auto flex items-center gap-3 sm:gap-5">
            {stopMsg && <span className="text-xs text-[#ffeb3b] max-w-40 truncate">{stopMsg}</span>}
            <Link
              to="/alarms"
              className={`hidden sm:flex items-center gap-2 ${worst === 'S3' ? 'animate-pulse' : ''}`}
              style={{ color: worst ? SEVERITY[worst].color : '#849396' }}
            >
              <AlertTriangle size={18} />
              <span className="text-sm font-bold">
                <span className="font-mono">{alarmCount}</span> {t('header.alarms')}
              </span>
            </Link>
            {can('owner_admin', 'operator') && (
              <button
                onClick={handleStopAll}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#ffb4ab] text-[#ffb4ab] hover:bg-[#ffb4ab] hover:text-[#410002] text-xs font-bold whitespace-nowrap transition-colors"
              >
                <OctagonX size={16} /> {t('header.stopAll')}
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6 pb-20 lg:pb-6">
          <Outlet />
        </main>

        {/* mobile bottom navigation */}
        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 h-16 bg-[#1c1b1b] border-t border-[#353534] grid grid-cols-4">
          {nav.slice(0, 4).map(({ key, path, icon: Icon, badge }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) => `flex flex-col items-center justify-center gap-1 text-[11px] relative ${isActive ? 'text-[#00e5ff]' : 'text-[#849396]'}`}
            >
              <Icon size={20} />
              {t(key)}
              {!!badge && (
                <span className="absolute top-1.5 start-1/2 ms-2 min-w-5 px-1 rounded-full text-[10px] font-bold font-mono text-[#0e0e0e]" style={{ backgroundColor: worst ? SEVERITY[worst].color : '#849396' }}>
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
