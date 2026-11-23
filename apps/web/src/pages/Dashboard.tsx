import { useEffect, useState } from 'react';
import { useFeature } from '../lib/features';
import { useSearchParams } from 'react-router-dom';
import { Gauge } from 'lucide-react';
import FarmMap from '../components/map/FarmMap';
import KPICard from '../components/KPICard';
import ZoneDrawer from '../components/ZoneDrawer';
import NextIrrigationCard from '../components/dashboard/NextIrrigationCard';
import DailyBriefingCard from '../components/ai/DailyBriefingCard';
import SuggestionCard from '../components/ai/SuggestionCard';
import { AlarmsCard, PumpsCard, StatusCard, TankCard, TrendsCard } from '../components/dashboard/SidePanel';
import { DropIcon, PumpIcon, ZonesIcon } from '../components/icons/FarmIcons';
import { useFarmConnector } from '../hooks/useFarmConnector';
import { fmtNum, useT } from '../lib/i18n';
import { fetchAiSuggestions, type AdvisorSuggestion } from '../lib/api';

const CYAN = '#00e5ff';
const GREY = '#849396';

export default function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedZone = searchParams.get('zone');
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([]);
  const { state, sendCommand } = useFarmConnector();
  const { t } = useT();
  const briefingOn = useFeature('ai.briefing');
  const advisorOn = useFeature('ai.advisor');

  const handleSelectZone = (id: string | null) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (id) next.set('zone', id);
        else next.delete('zone');
        return next;
      },
      { replace: true }
    );
  };

  useEffect(() => {
    let active = true;
    fetchAiSuggestions()
      .then((data) => {
        if (active && Array.isArray(data)) setSuggestions(data);
      })
      .catch(() => {
        if (!active) return;
        setSuggestions([]);
      });

    return () => {
      active = false;
    };
  }, []);

  const pumps = state?.pumps ?? [];
  const activePumps = pumps.filter((p) => p.state === 'running').length;
  const flowLmin = (state?.main_flow_m3h ?? 0) * (1000 / 60);
  const pressure = state?.main_pressure_bar ?? 0;
  const irrigating = (state?.zones ?? []).filter((z) => z.state === 'running').length;

  const handleSuggestionUpdate = (updated: AdvisorSuggestion) => {
    setSuggestions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  };

  const activeSuggestions = advisorOn ? suggestions.filter((s) => s.status === 'pending' || s.status === 'approved') : [];

  return (
    <div className="h-full flex flex-col gap-3 lg:gap-4">
      {/* Top Hero: Daily Briefing Card */}
      {briefingOn && <DailyBriefingCard />}

      {/* phones: status first */}
      <div className="lg:hidden space-y-3">
        <StatusCard state={state} />
        {activeSuggestions.length > 0 && (
          <div className="space-y-2">
            {activeSuggestions.map((sug) => (
              <SuggestionCard key={sug.id} suggestion={sug} onStatusChange={handleSuggestionUpdate} />
            ))}
          </div>
        )}
        <NextIrrigationCard />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard title={t('kpi.zonesRunning')} value={state ? irrigating : '--'} unit="/ 12" icon={<ZonesIcon size={18} />} color={irrigating ? CYAN : GREY} />
        <KPICard title={t('kpi.pumps')} value={state ? activePumps : '--'} unit={`/ ${pumps.length || 2}`} icon={<PumpIcon size={18} />} color={activePumps ? CYAN : GREY} />
        <KPICard title={t('kpi.flow')} value={state ? fmtNum(flowLmin) : '--'} unit="L/min" icon={<DropIcon size={18} />} color={flowLmin > 0 ? CYAN : GREY} />
        <KPICard title={t('kpi.pressure')} value={state ? fmtNum(pressure, 2) : '--'} unit="bar" icon={<Gauge size={18} />} color={pressure > 0.2 ? CYAN : GREY} />
      </div>

      <div className="flex-1 min-h-0 grid gap-3 lg:gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* the real farm is taller than wide (viewBox 900×980): give the map most of the screen height */}
        <div className="aspect-[900/980] lg:aspect-auto lg:min-h-[max(600px,calc(100dvh-7rem))]">
          <FarmMap state={state} selectedZone={selectedZone} onZoneSelect={handleSelectZone} />
        </div>
        <aside className="space-y-3 lg:overflow-y-auto lg:pe-1">
          {activeSuggestions.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-bold text-[#bac9cc] px-1">{t('advisor.title')}</div>
              {activeSuggestions.map((sug) => (
                <SuggestionCard key={sug.id} suggestion={sug} onStatusChange={handleSuggestionUpdate} />
              ))}
            </div>
          )}
          <NextIrrigationCard />
          <TankCard state={state} />
          <PumpsCard state={state} />
          <AlarmsCard alarms={state?.active_alarms ?? []} />
          <TrendsCard />
        </aside>
      </div>

      <ZoneDrawer
        zoneId={selectedZone}
        zoneState={state?.zones?.find((z) => z.zone_id === selectedZone)}
        onClose={() => handleSelectZone(null)}
        onCommand={sendCommand}
      />
    </div>
  );
}

