import { useState } from 'react';
import { AlertTriangle, CheckCircle, RefreshCw, Activity } from 'lucide-react';
import { useFarmConnector } from '../hooks/useFarmConnector';

interface AlarmEvent {
  id: string;
  timestamp: string;
  source: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'active' | 'acknowledged' | 'cleared';
}

const MOCK_ALARMS: AlarmEvent[] = [
  { id: 'ALM-1049', timestamp: '2026-04-19T08:34:12Z', source: 'PUMP-A', message: 'Pressure drop detected. Possible leak.', severity: 'critical', status: 'active' },
  { id: 'ALM-1048', timestamp: '2026-04-19T08:30:00Z', source: 'ZONE-8', message: 'Valve timeout. Did not reach open state.', severity: 'critical', status: 'active' },
  { id: 'ALM-1047', timestamp: '2026-04-19T07:15:22Z', source: 'SENSOR-M12', message: 'Moisture reading stale (>4h).', severity: 'warning', status: 'acknowledged' },
  { id: 'ALM-1046', timestamp: '2026-04-19T06:00:00Z', source: 'SYS', message: 'Daily cycle started successfully.', severity: 'info', status: 'cleared' },
];

export default function AlarmCenter() {
  const [filter, setFilter] = useState<'all' | 'critical' | 'warning'>('all');
  const { state } = useFarmConnector();
  
  // Combine mock alarms with any live backend structure that might come through
  const liveAlarms: AlarmEvent[] = (state?.active_alarms || []).map((a: any, i) => ({
    id: `LIVE-${i}`,
    timestamp: new Date().toISOString(),
    source: a.source || 'UNKNOWN',
    message: a.message || JSON.stringify(a),
    severity: a.severity || 'warning',
    status: 'active'
  }));

  const combinedAlarms = [...liveAlarms, ...MOCK_ALARMS];
  const filteredAlarms = combinedAlarms.filter(a => filter === 'all' || a.severity === filter);

  return (
    <div className="space-y-6 h-full flex flex-col font-sans">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1] tracking-wider flex items-center gap-3">
            <AlertTriangle className="text-[#ffb4ab]" size={28} />
            ALARM CENTER
          </h1>
          <p className="text-[#849396] mt-1 font-mono text-sm">EVENT LOG & FAULT DIAGNOSTICS</p>
        </div>
        
        <div className="flex gap-2 font-mono text-sm">
          <button 
            onClick={() => setFilter('all')}
            className={`px-4 py-2 border rounded ${filter === 'all' ? 'bg-[#353534] border-[#849396] text-[#e5e2e1]' : 'border-[#353534] text-[#849396] hover:bg-[#1c1b1b]'}`}
          >
            ALL
          </button>
          <button 
            onClick={() => setFilter('critical')}
            className={`px-4 py-2 border rounded ${filter === 'critical' ? 'bg-[#ffb4ab]/20 border-[#ffb4ab] text-[#ffb4ab]' : 'border-[#353534] text-[#ffb4ab] hover:bg-[#1c1b1b]'}`}
          >
            CRITICAL
          </button>
          <button 
            onClick={() => setFilter('warning')}
            className={`px-4 py-2 border rounded ${filter === 'warning' ? 'bg-[#ffeb3b]/20 border-[#ffeb3b] text-[#ffeb3b]' : 'border-[#353534] text-[#ffeb3b] hover:bg-[#1c1b1b]'}`}
          >
            WARNING
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 bg-[#0e0e0e] border border-[#353534] rounded-lg overflow-hidden flex flex-col relative before:absolute before:inset-0 before:bg-white/[0.02] before:pointer-events-none before:backdrop-blur-sm">
        <div className="grid grid-cols-12 gap-4 p-4 border-b border-[#353534] bg-[#1c1b1b] text-[#bac9cc] font-mono text-xs tracking-widest font-bold relative z-10">
          <div className="col-span-2">TIMESTAMP</div>
          <div className="col-span-2">SOURCE</div>
          <div className="col-span-1">SEVERITY</div>
          <div className="col-span-4">MESSAGE</div>
          <div className="col-span-1">STATUS</div>
          <div className="col-span-2 text-right">ACTIONS</div>
        </div>
        
        <div className="flex-1 overflow-y-auto relative z-10">
          {filteredAlarms.map((alarm) => (
            <div key={alarm.id} className="grid grid-cols-12 gap-4 p-4 border-b border-[#353534] text-sm items-center hover:bg-[#1c1b1b]/50 transition-colors">
              <div className="col-span-2 text-[#849396] font-mono">{alarm.timestamp.replace('T', ' ').replace('Z', '')}</div>
              <div className="col-span-2 font-bold font-mono text-[#e5e2e1]">{alarm.source}</div>
              <div className="col-span-1">
                <span className={`px-2 py-1 rounded text-xs font-bold font-mono tracking-wider ${
                  alarm.severity === 'critical' ? 'bg-[#ffb4ab]/10 text-[#ffb4ab] border border-[#ffb4ab]/30' :
                  alarm.severity === 'warning' ? 'bg-[#ffeb3b]/10 text-[#ffeb3b] border border-[#ffeb3b]/30' :
                  'bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/30'
                }`}>
                  {alarm.severity.toUpperCase()}
                </span>
              </div>
              <div className="col-span-4 text-[#e5e2e1] truncate" title={alarm.message}>{alarm.message}</div>
              <div className="col-span-1">
                <span className={`text-xs font-mono font-bold tracking-wider ${
                  alarm.status === 'active' ? 'text-[#ffb4ab] animate-pulse' :
                  alarm.status === 'acknowledged' ? 'text-[#ffeb3b]' :
                  'text-[#849396]'
                }`}>
                  {alarm.status.toUpperCase()}
                </span>
              </div>
              <div className="col-span-2 flex justify-end gap-2">
                {alarm.status === 'active' && (
                  <button className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#ffeb3b] text-[#ffeb3b] transition-colors" title="Acknowledge">
                    <CheckCircle size={16} />
                  </button>
                )}
                {alarm.status !== 'cleared' && (
                  <button className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded hover:border-[#00e5ff] text-[#00e5ff] transition-colors" title="Reset/Clear">
                    <RefreshCw size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
          {filteredAlarms.length === 0 && (
            <div className="p-8 text-center text-[#849396] font-mono">
              NO ALARMS MATCHING CRITERIA
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
