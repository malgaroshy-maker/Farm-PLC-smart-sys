import { useState } from 'react';
import { X, Activity, Droplet, Gauge, Thermometer, Play, Square } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

import type { ZoneLiveState } from '../hooks/useFarmConnector';
import type { CommandOutcome } from '../store/farm';
import { useAuth } from '../lib/auth';

interface ZoneDrawerProps {
  zoneId: string | null;
  zoneState?: ZoneLiveState;
  onClose: () => void;
  onCommand?: (action: 'start' | 'stop', targetId: string) => Promise<CommandOutcome>;
}

type Feedback = { kind: 'ok' | 'error'; text: string } | null;

// Sample shape only — real history arrives with telemetry storage (Milestone B).
const sampleChartData = [
  { time: '08:00', moisture: 45, pressure: 2.1 },
  { time: '09:00', moisture: 42, pressure: 2.1 },
  { time: '10:00', moisture: 38, pressure: 2.2 },
  { time: '11:00', moisture: 35, pressure: 0 },
  { time: '12:00', moisture: 55, pressure: 4.5 },
  { time: '13:00', moisture: 65, pressure: 4.4 },
  { time: '14:00', moisture: 60, pressure: 0 },
];

export default function ZoneDrawer(props: ZoneDrawerProps) {
  if (!props.zoneId) return null;
  // Keyed by zone so feedback resets when another zone is opened.
  return <ZoneDrawerBody key={props.zoneId} {...props} zoneId={props.zoneId} />;
}

function ZoneDrawerBody({ zoneId, zoneState, onClose, onCommand }: ZoneDrawerProps & { zoneId: string }) {
  const { can } = useAuth();
  const canControl = can('owner_admin', 'operator');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const run = async (action: 'start' | 'stop') => {
    if (!onCommand) return;
    setBusy(true);
    setFeedback(null);
    const res = await onCommand(action, zoneId);
    setBusy(false);
    setFeedback(
      res.ok
        ? { kind: 'ok', text: `${action === 'start' ? 'Start' : 'Stop'} command accepted` }
        : { kind: 'error', text: `Blocked: ${res.message}` },
    );
  };

  const isRunning = zoneState?.state === 'running';
  const stateLabel = (zoneState?.state ?? 'unknown').replace(/_/g, ' ').toUpperCase();
  const moisture = zoneState?.moisture_pct ? zoneState.moisture_pct.toFixed(1) : '--';
  const pressure = zoneState?.pressure_bar ? zoneState.pressure_bar.toFixed(2) : '--';
  const flow = zoneState?.flow_m3h ? Math.round(zoneState.flow_m3h * (1000/60)) : '--'; // L/min
  
  // Format uptime
  const uptimeStr = zoneState?.runtime_sec ? new Date(zoneState.runtime_sec * 1000).toISOString().substr(11, 8) : '00:00:00';

  return (
    <>
      <div 
        className="fixed inset-0 bg-[#0e0e0e]/80 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />
      
      <div className="fixed top-0 right-0 h-full w-[450px] bg-[#1c1b1b] border-l border-[#353534] shadow-2xl z-50 flex flex-col font-sans transform transition-transform text-[#e5e2e1]">
        {/* Header */}
        <div className="p-6 border-b border-[#353534] flex justify-between items-start bg-[#0e0e0e]">
          <div>
            <h2 className="text-2xl font-bold text-[#00e5ff] uppercase tracking-widest font-mono">
              {zoneId.replace('_', ' ')}
            </h2>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded text-xs font-bold font-mono tracking-wider border ${
                isRunning
                  ? 'bg-[#00e5ff]/10 text-[#00e5ff] border-[#00e5ff]/20'
                  : 'bg-[#849396]/10 text-[#849396] border-[#353534]'
              }`}>
                STATE: {stateLabel}
              </span>
              <span className="text-xs text-[#849396] font-mono border-l border-[#353534] pl-2">
                UPTIME: {uptimeStr}
              </span>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-[#849396] hover:text-[#e5e2e1] bg-[#1c1b1b] hover:bg-[#ffb4ab] hover:text-[#410002] p-2 rounded transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* Action Row */}
          <div className="border-b border-[#353534] pb-6 space-y-3">
            {canControl ? (
              <div className="flex gap-4">
                <button
                  disabled={busy}
                  onClick={() => run('start')}
                  className="flex-1 bg-[#1c1b1b] hover:bg-[#353534] disabled:opacity-50 border border-[#353534] hover:border-[#00e5ff] text-[#00e5ff] py-3 rounded flex items-center justify-center gap-2 font-bold font-mono tracking-wider transition-colors">
                  <Play size={18} /> START CYCLE
                </button>
                <button
                  disabled={busy}
                  onClick={() => run('stop')}
                  className="flex-1 bg-[#1c1b1b] hover:bg-[#353534] disabled:opacity-50 border border-[#353534] hover:border-[#ffb4ab] text-[#ffb4ab] py-3 rounded flex items-center justify-center gap-2 font-bold font-mono tracking-wider transition-colors">
                  <Square size={18} /> STOP ZONE
                </button>
              </div>
            ) : (
              <p className="text-xs font-mono text-[#849396]">VIEW ONLY — your role cannot issue commands.</p>
            )}
            {feedback && (
              <p role="status" className={`text-xs font-mono ${feedback.kind === 'ok' ? 'text-[#00e5ff]' : 'text-[#ffb4ab]'}`}>
                {feedback.text}
              </p>
            )}
          </div>

          {/* Live Metrics Grid */}
          <div className="grid grid-cols-2 gap-4">
            <MetricCard icon={<Droplet />} label="MOISTURE" value={moisture} unit="%" />
            <MetricCard icon={<Gauge />} label="PRESSURE" value={pressure} unit="BAR" />
            <MetricCard icon={<Activity />} label="FLOW RATE" value={flow} unit="L/MIN" />
            <MetricCard icon={<Thermometer />} label="SOIL TEMP" value="--" unit="°C" />
          </div>

          {/* Trends Graph */}
          <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4">
            <h3 className="text-xs text-[#bac9cc] font-bold font-mono tracking-widest mb-4 flex justify-between">
              <span>MOISTURE TREND (24H)</span>
              <span className="text-[#849396]">SAMPLE DATA</span>
            </h3>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sampleChartData}>
                  <defs>
                    <linearGradient id="colorMoisture" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#00e5ff" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="#849396" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#849396" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1c1b1b', border: '1px solid #353534', borderRadius: '4px' }}
                    itemStyle={{ color: '#00e5ff', fontWeight: 'bold' }}
                    labelStyle={{ color: '#bac9cc' }}
                  />
                  <Area type="monotone" dataKey="moisture" stroke="#00e5ff" strokeWidth={2} fillOpacity={1} fill="url(#colorMoisture)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Device Info */}
          <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4">
            <h3 className="text-xs text-[#bac9cc] font-bold font-mono tracking-widest mb-4">HARDWARE STATUS</h3>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex justify-between border-b border-[#353534] pb-2">
                <span className="text-[#849396]">VALVE ID</span>
                <span className="text-[#e5e2e1]">{zoneId}_vlv</span>
              </div>
              <div className="flex justify-between border-b border-[#353534] pb-2">
                <span className="text-[#849396]">VALVE STATE</span>
                <span className={isRunning ? "text-[#00e5ff]" : "text-[#849396]"}>{isRunning ? 'OPEN' : 'CLOSED'}</span>
              </div>
              <div className="flex justify-between pb-2">
                <span className="text-[#849396]">HEALTH</span>
                <span className={zoneState?.state === 'faulted' || zoneState?.health === 'critical' ? "text-[#ffb4ab]" : "text-[#00e5ff]"}>
                  {zoneState?.health?.toUpperCase() || 'OK'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({ icon, label, value, unit = '' }: { icon: React.ReactNode, label: string, value: string | number, unit?: string }) {
  return (
    <div className="bg-[#0e0e0e] border border-[#353534] rounded p-4 flex flex-col pt-5 relative overflow-hidden backdrop-blur-md">
      <div className={`absolute left-0 top-0 w-1 h-full bg-current text-[#00e5ff] opacity-50`} />
      <div className="text-[#00e5ff] mb-3 bg-[#1c1b1b] p-2 rounded self-start border border-[#353534]">{icon}</div>
      <div className="text-xs text-[#849396] font-bold font-mono mb-1 tracking-wider uppercase">{label}</div>
      <div className="text-2xl font-bold font-mono text-[#e5e2e1] drop-shadow-md">
        {value} <span className="text-sm text-[#bac9cc]">{unit}</span>
      </div>
    </div>
  );
}
