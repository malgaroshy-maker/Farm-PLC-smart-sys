import { useEffect, useState } from 'react';
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
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([]);
  const { state, sendCommand } = useFarmConnector();
  const { t } = useT();

  useEffect(() => {
    let active = true;
    fetchAiSuggestions()
      .then((data) => {
        if (active && Array.isArray(data)) setSuggestions(data);
      })
      .catch(() => {
        if (!active) return;
        // Default weather advisor suggestion example if none fetched
        setSuggestions([
          {
            id: 'sug_weather_01',
            program_id: 'prog_morning',
            program_name: 'برنامج الصباح',
            program_name_ar: 'برنامج الصباح',
            action: 'skip',
            adjustment_pct: -100,
            reason: 'High rain probability (80%, 3.5mm) forecasted at 06:00. Skipping morning irrigation to conserve water.',
            reason_ar: 'احتمال هطول أمطار بنسبة 80% (3.5 ملم) عند الساعة 06:00. يوصى بتخطي ري الصباح لتوفير المياه.',
            weather_summary: {
              condition: 'rain',
              temperature_c: 19,
              rain_probability_pct: 80,
              precipitation_mm: 3.5,
              et0_mm: 2.1,
            },
            effective_date: new Date().toISOString().slice(0, 10),
            status: 'pending',
            provider: 'APInex',
            model: 'free/gemini-3.8-flash',
            created_at: new Date().toISOString(),
          },
        ]);
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

  const activeSuggestions = suggestions.filter((s) => s.status === 'pending' || s.status === 'approved');

  return (
    <div className="h-full flex flex-col gap-3 lg:gap-4">
      {/* Top Hero: Daily Briefing Card */}
      <DailyBriefingCard />

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
        <div className="aspect-[1000/887] lg:aspect-auto lg:min-h-[560px]">
          <FarmMap state={state} selectedZone={selectedZone} onZoneSelect={setSelectedZone} />
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
        onClose={() => setSelectedZone(null)}
        onCommand={sendCommand}
      />
    </div>
  );
}

