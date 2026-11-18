import React from 'react';

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ReactNode;
  /** CSS colour for the accent bar, icon and value */
  color?: string;
}

/** Compact KPI tile. Logical (start/end) spacing so it mirrors correctly in RTL. */
export default function KPICard({ title, value, unit, icon, color = '#849396' }: KPICardProps) {
  return (
    <div className="panel px-4 py-3 flex items-center gap-3 relative overflow-hidden min-w-0">
      <div className="absolute inset-y-0 start-0 w-1 opacity-70" style={{ backgroundColor: color }} />
      <div className="p-2 rounded-lg bg-black/30 border border-white/5 shrink-0" style={{ color }}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs font-bold text-[#bac9cc] truncate">{title}</div>
        <div className="flex items-baseline gap-1.5" dir="ltr">
          <span className={`${String(value).length > 6 ? "text-base sm:text-lg" : "text-2xl"} font-bold font-mono leading-tight whitespace-nowrap`} style={{ color: value === '--' ? '#849396' : '#e5e2e1' }}>
            {value}
          </span>
          {unit && <span className="text-xs text-[#849396] font-bold">{unit}</span>}
        </div>
      </div>
    </div>
  );
}
