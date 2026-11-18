import { useState } from 'react';
import { AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import type { Alarm } from '@algaroshy/contracts';
import { useFarmConnector } from '../hooks/useFarmConnector';

interface AlarmRow {
  id: string;
  timestamp: string;
  source: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'active' | 'acknowledged' | 'cleared';
}

// Contract severities S0 (critical) … S3 (info) → display buckets.
const SEVERITY: Record<Alarm['severity'], AlarmRow['severity']> = {
  S0: 'critical',
  S1: 'critical',
  S2: 'warning',
  S3: 'info',
};

function toRow(a: Alarm): AlarmRow {
  return {
    id: a.id,
    timestamp: a.triggered_at,
    source: a.zone_id ?? a.device_id ?? 'SYSTEM',
    message: a.message_en ?? a.alarm_code,
    severity: SEVERITY[a.severity] ?? 'warning',
    status: a.status === 'active_unacked' || a.status === 'pending' ? 'active' : a.status === 'active_acked' ? 'acknowledged' : 'cleared',
  };
}

export default function AlarmCenter() {
  const [filter, setFilter] = useState<'all' | 'critical' | 'warning'>('all');
  const { state } = useFarmConnector();

  const alarms = (state?.active_alarms ?? []).map(toRow);
  const filteredAlarms = alarms.filter(a => filter === 'all' || a.severity === filter);

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
                  <button disabled className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded text-[#ffeb3b] opacity-50 cursor-not-allowed" title="Acknowledge (coming with the alarm engine)">
                    <CheckCircle size={16} />
                  </button>
                )}
                {alarm.status !== 'cleared' && (
                  <button disabled className="p-1.5 bg-[#1c1b1b] border border-[#353534] rounded text-[#00e5ff] opacity-50 cursor-not-allowed" title="Reset (coming with the alarm engine)">
                    <RefreshCw size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
          {filteredAlarms.length === 0 && (
            <div className="p-8 text-center text-[#849396] font-mono">
              {alarms.length === 0
                ? 'NO ACTIVE ALARMS — the alarm engine is not built yet (Milestone B)'
                : 'NO ALARMS MATCHING CRITERIA'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
