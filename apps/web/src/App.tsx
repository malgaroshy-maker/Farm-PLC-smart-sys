import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import AlarmCenter from './pages/AlarmCenter';
import SimulatorPanel from './pages/SimulatorPanel';
import ZonesPage from './pages/ZonesPage';
import EquipmentPage from './pages/EquipmentPage';
import EventsPage from './pages/EventsPage';
import { AuthProvider } from './lib/auth';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<DashboardLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="zones" element={<ZonesPage />} />
            <Route path="equipment" element={<EquipmentPage />} />
            <Route path="alarms" element={<AlarmCenter />} />
            <Route path="events" element={<EventsPage />} />
            <Route path="simulator" element={<SimulatorPanel />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
