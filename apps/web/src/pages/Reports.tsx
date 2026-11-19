import { useEffect, useState, useMemo } from 'react';
import { Download, BarChart3 } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  DailyIrrigationReportRow,
  WaterUsageReportRow,
  PumpRuntimeReportRow,
  AlarmHistoryReportRow,
} from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import { apiFetch, apiUrl, session } from '../lib/api';
import { useFarmClock } from '../lib/clock';
import { fmtNum, pickName, useT, type MsgKey } from '../lib/i18n';
import { ReportsIcon } from '../components/icons/FarmIcons';
import { CROP_ICON } from '../components/icons/cropIcon';

const SEED = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));
const CYAN = '#00e5ff';
const YELLOW = '#ffeb3b';
const GREEN = '#7ee787';
const RED = '#ff5449';

type ReportTab = 'daily' | 'water' | 'pumps' | 'alarms';
type RangePreset = 'today' | 'week' | 'month';

const PUMP_NAMES: Record<string, [string, string]> = {
  pump_booster_01: ['Booster pump', 'مضخة التعزيز'],
  pump_well_01: ['Well pump', 'مضخة البئر'],
};

export default function ReportsPage() {
  const { t, lang } = useT();
  const { farmNow } = useFarmClock(lang);

  const [tab, setTab] = useState<ReportTab>('daily');
  const [rangePreset, setRangePreset] = useState<RangePreset>('week');
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Compute dates in farm timezone (Africa/Tripoli)
  const { fromDate, toDate } = useMemo(() => {
    const to = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Africa/Tripoli',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(farmNow);

    const d = new Date(farmNow);
    if (rangePreset === 'today') {
      return { fromDate: to, toDate: to };
    }
    if (rangePreset === 'week') {
      d.setDate(d.getDate() - 6);
    } else {
      d.setDate(d.getDate() - 29);
    }
    const from = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Africa/Tripoli',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(d);

    return { fromDate: from, toDate: to };
  }, [farmNow, rangePreset]);

  // Report data states
  const [dailyData, setDailyData] = useState<DailyIrrigationReportRow[]>([]);
  const [waterData, setWaterData] = useState<WaterUsageReportRow[]>([]);
  const [pumpData, setPumpData] = useState<PumpRuntimeReportRow[]>([]);
  const [alarmData, setAlarmData] = useState<AlarmHistoryReportRow[]>([]);

  useEffect(() => {
    let active = true;
    const fetchReport = async () => {
      setLoading(true);
      try {
        const query = `from_date=${fromDate}&to_date=${toDate}`;
        if (tab === 'daily') {
          const res = await apiFetch<DailyIrrigationReportRow[]>(`/api/v1/reports/daily-irrigation?${query}`);
          if (active) setDailyData(res);
        } else if (tab === 'water') {
          const res = await apiFetch<WaterUsageReportRow[]>(`/api/v1/reports/water-usage?${query}`);
          if (active) setWaterData(res);
        } else if (tab === 'pumps') {
          const res = await apiFetch<PumpRuntimeReportRow[]>(`/api/v1/reports/pump-runtime?${query}`);
          if (active) setPumpData(res);
        } else if (tab === 'alarms') {
          const res = await apiFetch<AlarmHistoryReportRow[]>(`/api/v1/reports/alarm-history?${query}`);
          if (active) setAlarmData(res);
        }
      } catch {
        // network / API error
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchReport();
    return () => {
      active = false;
    };
  }, [tab, fromDate, toDate]);

  // CSV Export Download Handler
  const handleExportCsv = async () => {
    setDownloading(true);
    try {
      const endpoint =
        tab === 'daily'
          ? '/api/v1/reports/daily-irrigation'
          : tab === 'water'
          ? '/api/v1/reports/water-usage'
          : tab === 'pumps'
          ? '/api/v1/reports/pump-runtime'
          : '/api/v1/reports/alarm-history';

      const url = apiUrl(`${endpoint}?from_date=${fromDate}&to_date=${toDate}&format=csv&lang=${lang}`);
      const headers = new Headers();
      if (session.token) headers.set('Authorization', `Bearer ${session.token}`);

      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `report_${tab}_${fromDate}_${toDate}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  // Summaries
  const totalWater = useMemo(() => {
    if (tab === 'daily') return dailyData.reduce((s, r) => s + (r.total_water_m3 ?? 0), 0);
    if (tab === 'water') return waterData.reduce((s, r) => s + (r.total_water_m3 ?? 0), 0);
    return 0;
  }, [tab, dailyData, waterData]);

  const totalCycles = useMemo(() => {
    if (tab === 'daily') return dailyData.reduce((s, r) => s + (r.cycle_count ?? 0), 0);
    if (tab === 'water') return waterData.reduce((s, r) => s + (r.cycle_count ?? 0), 0);
    return 0;
  }, [tab, dailyData, waterData]);

  const completedCycles = useMemo(() => {
    if (tab === 'daily') return dailyData.reduce((s, r) => s + (r.completed_count ?? 0), 0);
    if (tab === 'water') return waterData.reduce((s, r) => s + (r.completed_count ?? 0), 0);
    return 0;
  }, [tab, dailyData, waterData]);

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pb-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#e5e2e1] flex items-center gap-2">
            <ReportsIcon size={24} accent={CYAN} />
            {t('reports.title')}
          </h1>
          <p className="text-xs text-[#849396]">{t('reports.subtitle')}</p>
        </div>

        {/* Date Presets & Export CSV */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex rounded-xl bg-white/5 border border-white/10 p-0.5">
            {(['today', 'week', 'month'] as RangePreset[]).map((r) => (
              <button
                key={r}
                onClick={() => setRangePreset(r)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  rangePreset === r
                    ? 'bg-[#00e5ff] text-black shadow'
                    : 'text-[#849396] hover:text-[#e5e2e1]'
                }`}
              >
                {t(`reports.range.${r}` as MsgKey)}
              </button>
            ))}
          </div>

          <button
            onClick={handleExportCsv}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-[#00e5ff] hover:bg-white/10 transition-colors"
          >
            <Download size={14} />
            {downloading ? t('common.loading') : t('reports.exportCsv')}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 pb-2 overflow-x-auto">
        {(['daily', 'water', 'pumps', 'alarms'] as ReportTab[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
              tab === k
                ? 'bg-white/10 text-[#00e5ff] border border-[#00e5ff]/30'
                : 'text-[#849396] hover:text-[#e5e2e1]'
            }`}
          >
            {t(`reports.tab.${k}` as MsgKey)}
          </button>
        ))}
      </div>

      {/* Summary KPI Cards (for daily & water) */}
      {(tab === 'daily' || tab === 'water') && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="panel p-4">
            <div className="text-xs text-[#849396]">{t('reports.totalWater')}</div>
            <div className="text-2xl font-bold font-mono text-[#00e5ff] mt-1" dir="ltr">
              {fmtNum(totalWater, 2)} <span className="text-xs text-[#849396]">m³</span>
            </div>
          </div>
          <div className="panel p-4">
            <div className="text-xs text-[#849396]">{t('reports.totalCycles')}</div>
            <div className="text-2xl font-bold font-mono text-[#e5e2e1] mt-1" dir="ltr">
              {totalCycles}
            </div>
          </div>
          <div className="panel p-4">
            <div className="text-xs text-[#849396]">{t('reports.completedCycles')}</div>
            <div className="text-2xl font-bold font-mono text-[#7ee787] mt-1" dir="ltr">
              {completedCycles}
            </div>
          </div>
        </div>
      )}

      {/* Charts Section */}
      <div className="panel p-4 space-y-3">
        <div className="text-xs font-bold text-[#bac9cc] flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <BarChart3 size={15} className="text-[#00e5ff]" />
            {t(`reports.tab.${tab}` as MsgKey)}
          </span>
          <span className="text-[11px] font-mono text-[#849396]">
            {fromDate} → {toDate}
          </span>
        </div>

        <div className="h-64 sm:h-72 w-full pt-2" dir="ltr">
          {loading ? (
            <div className="h-full flex items-center justify-center text-xs text-[#849396]">
              {t('common.loading')}
            </div>
          ) : tab === 'daily' ? (
            dailyData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-[#849396]">
                {t('reports.noData')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="date" stroke="#849396" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#849396" fontSize={11} tickLine={false} axisLine={false} width={40} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161618',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 10,
                    }}
                    labelStyle={{ color: '#bac9cc' }}
                  />
                  <Legend />
                  <Bar dataKey="total_water_m3" name={t('reports.chartWater')} fill={CYAN} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="completed_count" name={t('reports.chartCompleted')} fill={GREEN} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          ) : tab === 'water' ? (
            waterData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-[#849396]">
                {t('reports.noData')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={waterData.map((r) => {
                    const seed = SEED[r.zone_id];
                    return {
                      ...r,
                      name: seed ? pickName(lang, seed.name, seed.name_ar) : r.zone_id,
                    };
                  })}
                  layout="vertical"
                  margin={{ left: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" horizontal={false} />
                  <XAxis type="number" stroke="#849396" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#bac9cc"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161618',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 10,
                    }}
                    labelStyle={{ color: '#bac9cc' }}
                  />
                  <Bar dataKey="total_water_m3" name={t('reports.chartWater')} fill={CYAN} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          ) : tab === 'pumps' ? (
            pumpData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-[#849396]">
                {t('reports.noData')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={pumpData.map((p) => {
                    const [en, ar] = PUMP_NAMES[p.pump_id] ?? [p.pump_id, p.pump_id];
                    return {
                      ...p,
                      name: lang === 'ar' ? ar : en,
                    };
                  })}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="name" stroke="#849396" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#849396" fontSize={11} tickLine={false} axisLine={false} width={40} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161618',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 10,
                    }}
                    labelStyle={{ color: '#bac9cc' }}
                  />
                  <Legend />
                  <Bar dataKey="runtime_hours" name={t('reports.chartRuntime')} fill={CYAN} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="start_count" name={t('reports.chartStarts')} fill={YELLOW} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          ) : (
            alarmData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-[#849396]">
                {t('reports.noData')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={alarmData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="alarm_code" stroke="#849396" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#849396" fontSize={11} tickLine={false} axisLine={false} width={30} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161618',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 10,
                    }}
                    labelStyle={{ color: '#bac9cc' }}
                  />
                  <Bar dataKey="count" name={t('reports.chartOccurrences')} fill={RED} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          )}
        </div>
      </div>

      {/* Data Table Section */}
      <div className="panel overflow-hidden">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-xs font-bold text-[#bac9cc]">{t('reports.detailedRecords')}</span>
        </div>

        <div className="overflow-x-auto">
          {tab === 'daily' && (
            <table className="w-full text-xs text-start">
              <thead className="bg-white/5 text-[#849396] font-bold border-b border-white/5">
                <tr>
                  <th className="p-3 text-start">{t('reports.date')}</th>
                  <th className="p-3 text-end">{t('reports.waterM3')}</th>
                  <th className="p-3 text-end">{t('reports.totalCycles')}</th>
                  <th className="p-3 text-end">{t('reports.completedCycles')}</th>
                  <th className="p-3 text-end">{t('reports.abortedCycles')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {dailyData.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-[#849396]">
                      {t('reports.noData')}
                    </td>
                  </tr>
                ) : (
                  dailyData.map((row) => (
                    <tr key={row.date} className="hover:bg-white/5">
                      <td className="p-3 font-mono text-[#e5e2e1]">{row.date}</td>
                      <td className="p-3 text-end font-mono text-[#00e5ff]">{fmtNum(row.total_water_m3, 2)}</td>
                      <td className="p-3 text-end font-mono">{row.cycle_count ?? 0}</td>
                      <td className="p-3 text-end font-mono text-[#7ee787]">{row.completed_count ?? 0}</td>
                      <td className="p-3 text-end font-mono text-[#ff5449]">
                        {(row.aborted_count ?? 0) + (row.skipped_count ?? 0) + (row.faulted_count ?? 0) + (row.manual_stop_count ?? 0)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}

          {tab === 'water' && (
            <table className="w-full text-xs text-start">
              <thead className="bg-white/5 text-[#849396] font-bold border-b border-white/5">
                <tr>
                  <th className="p-3 text-start">{t('reports.zone')}</th>
                  <th className="p-3 text-start">{t('reports.crop')}</th>
                  <th className="p-3 text-end">{t('reports.waterM3')}</th>
                  <th className="p-3 text-end">{t('reports.totalCycles')}</th>
                  <th className="p-3 text-end">{t('reports.duration')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {waterData.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-[#849396]">
                      {t('reports.noData')}
                    </td>
                  </tr>
                ) : (
                  waterData.map((row) => {
                    const seed = SEED[row.zone_id];
                    const Crop = seed ? CROP_ICON[seed.crop_type] : null;
                    const zName = seed ? pickName(lang, seed.name, seed.name_ar) : row.zone_id;

                    return (
                      <tr key={row.zone_id} className="hover:bg-white/5">
                        <td className="p-3 font-bold text-[#e5e2e1]">{zName}</td>
                        <td className="p-3 flex items-center gap-1.5 text-[#bac9cc]">
                          {Crop && <Crop size={14} />}
                          <span>{seed ? t(`crop.${seed.crop_type}` as MsgKey) : '—'}</span>
                        </td>
                        <td className="p-3 text-end font-mono text-[#00e5ff]">{fmtNum(row.total_water_m3, 2)}</td>
                        <td className="p-3 text-end font-mono">{row.cycle_count}</td>
                        <td className="p-3 text-end font-mono">{row.total_duration_min} min</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'pumps' && (
            <table className="w-full text-xs text-start">
              <thead className="bg-white/5 text-[#849396] font-bold border-b border-white/5">
                <tr>
                  <th className="p-3 text-start">{t('reports.pump')}</th>
                  <th className="p-3 text-end">{t('reports.runtimeHours')}</th>
                  <th className="p-3 text-end">{t('reports.starts')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {pumpData.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-6 text-center text-[#849396]">
                      {t('reports.noData')}
                    </td>
                  </tr>
                ) : (
                  pumpData.map((row) => {
                    const [en, ar] = PUMP_NAMES[row.pump_id] ?? [row.pump_id, row.pump_id];
                    return (
                      <tr key={row.pump_id} className="hover:bg-white/5">
                        <td className="p-3 font-bold text-[#e5e2e1]">{lang === 'ar' ? ar : en}</td>
                        <td className="p-3 text-end font-mono text-[#00e5ff]">{fmtNum(row.runtime_hours, 2)} h</td>
                        <td className="p-3 text-end font-mono text-[#ffeb3b]">{row.start_count}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'alarms' && (
            <table className="w-full text-xs text-start">
              <thead className="bg-white/5 text-[#849396] font-bold border-b border-white/5">
                <tr>
                  <th className="p-3 text-start">{t('reports.alarmCode')}</th>
                  <th className="p-3 text-start">{t('reports.alarmTitle')}</th>
                  <th className="p-3 text-start">{t('reports.severity')}</th>
                  <th className="p-3 text-end">{t('reports.count')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {alarmData.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-6 text-center text-[#849396]">
                      {t('reports.noData')}
                    </td>
                  </tr>
                ) : (
                  alarmData.map((row) => (
                    <tr key={row.alarm_code} className="hover:bg-white/5">
                      <td className="p-3 font-mono font-bold text-[#ff5449]">{row.alarm_code}</td>
                      <td className="p-3 text-[#e5e2e1]">{lang === 'ar' ? row.title_ar : row.title}</td>
                      <td className="p-3 font-bold">{row.severity}</td>
                      <td className="p-3 text-end font-mono font-bold">{row.count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
