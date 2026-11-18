import { useState } from 'react';
import { Droplet, Power, CloudRain, ShieldCheck, AlertTriangle, Gauge } from 'lucide-react';
import { SEVERITY, topSeverity } from '../lib/alarms';
import LiveMap from '../components/LiveMap';
import KPICard from '../components/KPICard';
import ZoneDrawer from '../components/ZoneDrawer';
import { useFarmConnector } from '../hooks/useFarmConnector';

export default function Dashboard() {
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const { state, connected, sendCommand } = useFarmConnector();

  const activePumps = state?.pumps?.filter(p => p.state === 'running').length || 0;
  const totalPumps = state?.pumps?.length || 2;
  const flowRate = state?.main_flow_m3h ? Math.round(state.main_flow_m3h * (1000/60)) : 0;
  const worst = state ? topSeverity(state.active_alarms) : null;
  const systemHealth = worst ? `${state?.active_alarms.length} · ${SEVERITY[worst].label}` : 'OK';
  const healthColor = worst === 'S3' || worst === 'S2' ? 'text-[#ffb4ab]' : worst === 'S1' ? 'text-[#ffeb3b]' : 'text-[#00e5ff]';
  const pressure = state?.main_pressure_bar ?? 0;

  return (
    <div className="space-y-6 h-full flex flex-col font-sans">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1] tracking-wider font-mono">
            SYSTEM OVERVIEW
            {!connected && <span className="ml-4 text-sm text-[#ffb4ab] border border-[#ffb4ab] rounded px-2 py-1 animate-pulse">OFFLINE</span>}
          </h1>
          <p className="text-[#849396] mt-1 font-mono text-sm uppercase">Main Irrigation Control Panel</p>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-6">
        <KPICard 
          title="ACTIVE PUMPS" 
          value={activePumps} 
          unit={`/ ${totalPumps}`} 
          icon={<Power />} 
          statusColor={activePumps > 0 ? "text-[#00e5ff]" : "text-[#849396]"}
        />
        <KPICard 
          title="FLOW RATE" 
          value={flowRate} 
          unit="L/min" 
          icon={<Droplet />} 
          statusColor={flowRate > 0 ? "text-[#00e5ff]" : "text-[#849396]"}
        />
        <KPICard
          title="MAIN PRESSURE"
          value={pressure.toFixed(2)}
          unit="bar"
          icon={<Gauge />}
          statusColor={pressure > 0.2 ? "text-[#00e5ff]" : "text-[#849396]"}
        />
        <KPICard 
          title="TANK LEVEL" 
          value={state?.tank_level_pct ? state.tank_level_pct.toFixed(1) : 0} 
          unit="%" 
          icon={<CloudRain />} 
          statusColor={(state?.tank_level_pct ?? 100) < 10 ? "text-[#ffb4ab]" : (state?.tank_level_pct ?? 100) < 25 ? "text-[#ffeb3b]" : "text-[#00e5ff]"}
        />
        <KPICard 
          title="SYSTEM HEALTH" 
          value={systemHealth} 
          icon={state?.active_alarms?.length ? <AlertTriangle /> : <ShieldCheck />} 
          statusColor={healthColor}
        />
      </div>

      {/* Main Map Region */}
      <div className="flex-1 min-h-0 relative">
        <div className="h-full">
          <LiveMap 
            onZoneSelect={(id) => setSelectedZone(id)} 
            zoneStates={state?.zones || []} 
          />
        </div>
      </div>

      {/* Side Drawer for Zone Details */}
      <ZoneDrawer 
        zoneId={selectedZone}
        zoneState={state?.zones?.find(z => z.zone_id === selectedZone)}
        onClose={() => setSelectedZone(null)} 
        onCommand={sendCommand}
      />
    </div>
  );
}
