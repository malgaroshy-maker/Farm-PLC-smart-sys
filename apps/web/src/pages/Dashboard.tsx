import { useState } from 'react';
import { Gauge } from 'lucide-react';
import FarmMap from '../components/map/FarmMap';
import KPICard from '../components/KPICard';
import ZoneDrawer from '../components/ZoneDrawer';
import { AlarmsCard, PumpsCard, StatusCard, TankCard, TrendsCard } from '../components/dashboard/SidePanel';
import { DropIcon, PumpIcon, ZonesIcon } from '../components/icons/FarmIcons';
import { useFarmConnector } from '../hooks/useFarmConnector';
import { fmtNum, useT } from '../lib/i18n';

const CYAN = '#00e5ff';
const GREY = '#849396';

export default function Dashboard() {
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const { state, sendCommand } = useFarmConnector();
  const { t } = useT();

  const pumps = state?.pumps ?? [];
  const activePumps = pumps.filter((p) => p.state === 'running').length;
  const flowLmin = (state?.main_flow_m3h ?? 0) * (1000 / 60);
  const pressure = state?.main_pressure_bar ?? 0;
  const irrigating = (state?.zones ?? []).filter((z) => z.state === 'running').length;

  return (
    <div className="h-full flex flex-col gap-3 lg:gap-4">
      {/* phones: status first */}
      <div className="lg:hidden">
        <StatusCard state={state} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard title={t('kpi.zonesRunning')} value={state ? irrigating : '--'} unit="/ 12" icon={<ZonesIcon size={18} />} color={irrigating ? CYAN : GREY} />
        <KPICard title={t('kpi.pumps')} value={state ? activePumps : '--'} unit={`/ ${pumps.length || 2}`} icon={<PumpIcon size={18} />} color={activePumps ? CYAN : GREY} />
        <KPICard title={t('kpi.flow')} value={state ? fmtNum(flowLmin) : '--'} unit="L/min" icon={<DropIcon size={18} />} color={flowLmin > 0 ? CYAN : GREY} />
        <KPICard title={t('kpi.pressure')} value={state ? fmtNum(pressure, 2) : '--'} unit="bar" icon={<Gauge size={18} />} color={pressure > 0.2 ? CYAN : GREY} />
      </div>

      <div className="flex-1 min-h-0 grid gap-3 lg:gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="aspect-[1000/887] lg:aspect-auto lg:min-h-[560px]">
          <FarmMap state={state} selectedZone={selectedZone} onZoneSelect={setSelectedZone} />
        </div>
        <aside className="space-y-3 lg:overflow-y-auto lg:pe-1">
          <TankCard state={state} />
          <PumpsCard state={state} />
          <AlarmsCard alarms={state?.active_alarms ?? []} />
          <TrendsCard />
        </aside>
      </div>

      <ZoneDrawer
        zoneId={selectedZone}
        zoneState={state?.zones?.find((z) => z.zone_id === selectedZone)}
        onClose={() => setSelectedZone(null)}
        onCommand={sendCommand}
      />
    </div>
  );
}

