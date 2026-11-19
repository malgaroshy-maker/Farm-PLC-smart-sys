import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import AlarmCenter from './pages/AlarmCenter';
import ZonesPage from './pages/ZonesPage';
import EquipmentPage from './pages/EquipmentPage';
import EventsPage from './pages/EventsPage';
import { AuthProvider } from './lib/auth';

const SchedulesPage = lazy(() => import('./pages/Schedules'));
const ReportsPage = lazy(() => import('./pages/Reports'));
const SimulatorPanel = lazy(() => import('./pages/SimulatorPanel'));

function PageLoader() {
  return (
    <div className="h-full w-full flex items-center justify-center text-xs text-[#849396]">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-[#00e5ff] animate-ping" />
        <span>جارٍ التحميل…</span>
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<DashboardLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="zones" element={<ZonesPage />} />
              <Route path="schedules" element={<SchedulesPage />} />
              <Route path="equipment" element={<EquipmentPage />} />
              <Route path="alarms" element={<AlarmCenter />} />
              <Route path="events" element={<EventsPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="simulator" element={<SimulatorPanel />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Router>
    </AuthProvider>
  );
}

export default App;
