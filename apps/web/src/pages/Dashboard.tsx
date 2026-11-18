import { useState } from 'react';
import { AlertTriangle, CloudRain, Droplet, Gauge, Power, ShieldCheck, Sprout } from 'lucide-react';
import FarmMap from '../components/map/FarmMap';
import KPICard from '../components/KPICard';
import ZoneDrawer from '../components/ZoneDrawer';
import { useFarmConnector } from '../hooks/useFarmConnector';
import { SEVERITY, topSeverity } from '../lib/alarms';
import { fmtNum, useT } from '../lib/i18n';

const CYAN = '#00e5ff';
const GREY = '#849396';

export default function Dashboard() {
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const { state, sendCommand } = useFarmConnector();
  const { t, lang } = useT();

  const pumps = state?.pumps ?? [];
  const activePumps = pumps.filter((p) => p.state === 'running').length;
  const flowLmin = (state?.main_flow_m3h ?? 0) * (1000 / 60);
  const pressure = state?.main_pressure_bar ?? 0;
  const tank = state?.tank_level_pct;
  const irrigating = (state?.zones ?? []).filter((z) => z.state === 'running').length;
  const worst = state ? topSeverity(state.active_alarms) : null;
  const healthColor = worst ? SEVERITY[worst].color : CYAN;
  const healthText = worst
    ? `${state?.active_alarms.length} · ${lang === 'ar' ? SEVERITY[worst].labelAr : SEVERITY[worst].label}`
    : t('kpi.ok');

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <KPICard title={t('kpi.zonesRunning')} value={state ? irrigating : '--'} unit="/ 12" icon={<Sprout size={18} />} color={irrigating ? CYAN : GREY} />
        <KPICard title={t('kpi.pumps')} value={state ? activePumps : '--'} unit={`/ ${pumps.length || 2}`} icon={<Power size={18} />} color={activePumps ? CYAN : GREY} />
        <KPICard title={t('kpi.flow')} value={state ? fmtNum(flowLmin) : '--'} unit="L/min" icon={<Droplet size={18} />} color={flowLmin > 0 ? CYAN : GREY} />
        <KPICard title={t('kpi.pressure')} value={state ? fmtNum(pressure, 2) : '--'} unit="bar" icon={<Gauge size={18} />} color={pressure > 0.2 ? CYAN : GREY} />
        <KPICard
          title={t('kpi.tank')}
          value={tank != null ? fmtNum(tank, 1) : '--'}
          unit="%"
          icon={<CloudRain size={18} />}
          color={tank == null ? GREY : tank < 10 ? SEVERITY.S3.color : tank < 25 ? SEVERITY.S1.color : CYAN}
        />
        <KPICard
          title={t('kpi.health')}
          value={state ? healthText : '--'}
          icon={worst ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
          color={healthColor}
        />
      </div>

      <div className="aspect-[1000/887] lg:aspect-auto lg:flex-1 lg:min-h-[520px]">
        <FarmMap state={state} selectedZone={selectedZone} onZoneSelect={setSelectedZone} />
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
