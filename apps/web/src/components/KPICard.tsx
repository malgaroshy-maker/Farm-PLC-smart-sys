import React from 'react';

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  statusColor?: string;
}

export default function KPICard({ title, value, unit, icon, trend, trendUp, statusColor = 'text-[#00e5ff]' }: KPICardProps) {
  return (
    <div className="bg-[#1c1b1b] border border-[#353534] rounded-xl p-5 flex flex-col relative overflow-hidden shadow-lg backdrop-blur-md">
      <div className={`absolute left-0 top-0 w-1 h-full bg-current ${statusColor} opacity-50`} />
      
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-sm font-bold text-[#bac9cc] tracking-widest font-mono uppercase truncate pr-4">{title}</h3>
        <div className={`p-2 rounded bg-[#0e0e0e] border border-[#353534] ${statusColor}`}>
          {icon}
        </div>
      </div>
      
      <div className="flex items-end gap-2 mt-auto">
        <span className="text-3xl font-bold text-[#e5e2e1] leading-none font-mono tracking-tight drop-shadow-md">{value}</span>
        {unit && <span className="text-sm text-[#849396] font-bold mb-1">{unit}</span>}
      </div>

      {trend && (
        <div className="mt-3 text-[10px] font-mono flex items-center gap-1 uppercase tracking-wider">
          <span className={trendUp ? 'text-[#ffc948]' : 'text-[#ffb4ab]'}>
            {trendUp ? '▲' : '▼'} {trend}
          </span>
          <span className="text-[#849396]">vs avg baseline</span>
        </div>
      )}
    </div>
  );
}
