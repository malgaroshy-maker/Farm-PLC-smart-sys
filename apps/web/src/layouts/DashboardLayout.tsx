import { useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, AlertTriangle, LogOut, Settings } from 'lucide-react';

export default function DashboardLayout() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const isAuth = localStorage.getItem('auth');
    if (isAuth !== 'true') {
      navigate('/login');
    }
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('auth');
    navigate('/login');
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
          <div className="flex items-center gap-2 mt-2">
            <div className="w-2 h-2 rounded-full bg-[#00e5ff] animate-pulse glow" />
            <span className="text-xs text-[#00e5ff] tracking-widest font-mono">SYS.ONLINE</span>
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
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-md text-[#849396] hover:bg-[#353534] hover:text-[#ffb4ab] transition-colors"
          >
            <LogOut size={20} />
            <span className="font-medium">Logout Admin</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-b border-[#353534] bg-[#0e0e0e] flex items-center justify-between px-8">
          <div className="flex items-center gap-4">
            <span className="text-sm text-[#849396] font-mono">
              {new Date().toISOString().split('T')[0]} / {new Date().toISOString().split('T')[1].substring(0, 8)} UTC
            </span>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-[#ffeb3b]">
              <AlertTriangle size={18} />
              <span className="text-sm font-bold font-mono">2 WARNINGS</span>
            </div>
            <button className="text-[#849396] hover:text-[#e5e2e1] transition-colors">
              <Settings size={20} />
            </button>
          </div>
        </header>

        {/* Dynamic Route Content */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#0e0e0e]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
