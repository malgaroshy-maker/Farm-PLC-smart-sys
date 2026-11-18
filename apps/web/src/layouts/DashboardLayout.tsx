import { useEffect, useState } from 'react';
import { Navigate, Outlet, Link, useLocation } from 'react-router-dom';
import { Activity, AlertTriangle, LogOut, OctagonX } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { session } from '../lib/api';
import { useFarmStore } from '../store/farm';
import type { LinkStatus } from '../store/farm';

const LINK_LABEL: Record<LinkStatus, { text: string; color: string }> = {
  idle: { text: 'SYS.IDLE', color: '#849396' },
  connecting: { text: 'SYS.CONNECTING', color: '#ffeb3b' },
  live: { text: 'SYS.LIVE', color: '#00e5ff' },
  polling: { text: 'SYS.POLLING', color: '#ffeb3b' },
  offline: { text: 'SYS.OFFLINE', color: '#ffb4ab' },
};

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export default function DashboardLayout() {
  const location = useLocation();
  const { user, loading, logout, can } = useAuth();
  const connect = useFarmStore((s) => s.connect);
  const disconnect = useFarmStore((s) => s.disconnect);
  const link = useFarmStore((s) => s.link);
  const fresh = useFarmStore((s) => s.state?.data_fresh ?? false);
  const alarmCount = useFarmStore((s) => s.state?.active_alarms.length ?? 0);
  const sendCommand = useFarmStore((s) => s.sendCommand);
  const [stopMsg, setStopMsg] = useState<string | null>(null);
  const now = useClock();

  useEffect(() => {
    if (user && session.token) connect(session.token);
    return () => disconnect();
  }, [user, connect, disconnect]);

  if (loading) {
    return <div className="h-screen bg-[#0e0e0e] text-[#849396] font-mono flex items-center justify-center">RESTORING SESSION…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;

  const status = link === 'live' || link === 'polling'
    ? (fresh ? LINK_LABEL[link] : { text: 'SIM.STALE', color: '#ffb4ab' })
    : LINK_LABEL[link];

  const handleStopAll = async () => {
    if (!window.confirm('Stop ALL running zones?')) return;
    const res = await sendCommand({ command_type: 'stop_all', target_type: 'system' });
    setStopMsg(res.ok ? 'STOP ALL sent' : `STOP ALL failed: ${res.message}`);
    setTimeout(() => setStopMsg(null), 4000);
  };

  const navItems = [
    { name: 'Dashboard', path: '/', icon: Activity },
    { name: 'Alarm Center', path: '/alarms', icon: AlertTriangle },
  ];

  return (
    <div className="flex h-screen bg-[#0e0e0e] text-[#e5e2e1] font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[#353534] bg-[#1c1b1b] flex flex-col">
        <div className="p-6 border-b border-[#353534]">
          <h1 className="text-xl font-bold tracking-wider text-[#00e5ff]">
            FARM-PLC <span className="text-[#849396] text-sm">HMI</span>
          </h1>
          <div className="flex items-center gap-2 mt-2" title={`Link: ${link}`}>
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: status.color }} />
            <span className="text-xs tracking-widest font-mono" style={{ color: status.color }}>{status.text}</span>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
                  isActive
                    ? 'bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/30'
                    : 'text-[#bac9cc] hover:bg-[#353534] hover:text-[#e5e2e1]'
                }`}
              >
                <Icon size={20} />
                <span className="font-medium">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[#353534]">
          <div className="px-4 pb-3 text-xs font-mono text-[#849396]">
            <div className="text-[#e5e2e1]">{user.name}</div>
            <div className="uppercase tracking-wider">{user.role.replace('_', ' ')}</div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-md text-[#849396] hover:bg-[#353534] hover:text-[#ffb4ab] transition-colors"
          >
            <LogOut size={20} />
            <span className="font-medium">Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-[#353534] bg-[#0e0e0e] flex items-center justify-between px-8">
          <span className="text-sm text-[#849396] font-mono">
            {now.toISOString().split('T')[0]} / {now.toISOString().split('T')[1].substring(0, 8)} UTC
          </span>
          <div className="flex items-center gap-6">
            {stopMsg && <span className="text-xs font-mono text-[#ffeb3b]">{stopMsg}</span>}
            <Link to="/alarms" className={`flex items-center gap-2 ${alarmCount ? 'text-[#ffb4ab]' : 'text-[#849396]'}`}>
              <AlertTriangle size={18} />
              <span className="text-sm font-bold font-mono">{alarmCount} ALARMS</span>
            </Link>
            {can('owner_admin', 'operator') && (
              <button
                onClick={handleStopAll}
                className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#ffb4ab] text-[#ffb4ab] hover:bg-[#ffb4ab] hover:text-[#410002] font-mono text-xs font-bold tracking-wider transition-colors"
                title="Stop every running zone"
              >
                <OctagonX size={16} /> STOP ALL
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-8 bg-[#0e0e0e]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
