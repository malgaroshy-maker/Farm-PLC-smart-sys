import { useEffect, useState } from 'react';
import { Plus, Trash2, Edit2, AlertTriangle, Check, Clock, Calendar } from 'lucide-react';
import type { ConflictError, Program, ProgramCreate } from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import { apiFetch } from '../lib/api';
import { useAuth } from '../lib/auth';
import { pickName, useT, type MsgKey } from '../lib/i18n';
import { ScheduleIcon, AiSparklesIcon } from '../components/icons/FarmIcons';
import { CROP_ICON } from '../components/icons/cropIcon';
import SuggestionCard from '../components/ai/SuggestionCard';
import { fetchAiSuggestions, type AdvisorSuggestion } from '../lib/api';

const SEED = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));
const CYAN = '#00e5ff';

const DAYS: { dayNum: number; key: MsgKey }[] = [
  { dayNum: 1, key: 'days.mon' },
  { dayNum: 2, key: 'days.tue' },
  { dayNum: 3, key: 'days.wed' },
  { dayNum: 4, key: 'days.thu' },
  { dayNum: 5, key: 'days.fri' },
  { dayNum: 6, key: 'days.sat' },
  { dayNum: 7, key: 'days.sun' },
];

function parseDays(maskStr: string | undefined): number[] {
  if (!maskStr) return [1, 2, 3, 4, 5, 6, 7];
  return maskStr
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((n) => n >= 1 && n <= 7);
}

function formatDays(days: number[]): string {
  return [...days].sort((a, b) => a - b).join(',');
}

const PRESETS = [15, 30, 45, 60];

interface StepDraft {
  zone_id: string;
  duration_min: number;
}

export default function SchedulesPage() {
  const { t, lang, isRtl } = useT();
  const { can } = useAuth();
  const isAdmin = can('owner_admin');
  const canToggle = can('owner_admin', 'operator');

  const [programs, setPrograms] = useState<Program[]>([]);
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProgram, setSelectedProgram] = useState<Program | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    let active = true;
    fetchAiSuggestions()
      .then((data) => {
        if (active && Array.isArray(data)) setSuggestions(data);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    apiFetch<Program[]>('/api/v1/schedules')
      .then((data) => {
        if (active) setPrograms(data);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshPrograms = async () => {
    try {
      const data = await apiFetch<Program[]>('/api/v1/schedules');
      setPrograms(data);
    } catch {
      // Offline or network error
    }
  };

  const handleToggle = async (p: Program) => {
    if (!canToggle) return;
    try {
      const updated = await apiFetch<Program>(`/api/v1/schedules/${p.id}/toggle`, {
        method: 'PATCH',
      });
      setPrograms((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Toggle failed');
    }
  };

  const openNewDrawer = () => {
    if (!isAdmin) return;
    setSelectedProgram(null);
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (p: Program) => {
    if (!isAdmin) return;
    setSelectedProgram(p);
    setIsDrawerOpen(true);
  };

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#e5e2e1] flex items-center gap-2">
            <ScheduleIcon size={24} accent={CYAN} />
            {t('schedules.title')}
          </h1>
          <p className="text-xs text-[#849396]">{t('schedules.subtitle')}</p>
        </div>
        {isAdmin && (
          <button
            onClick={openNewDrawer}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#00e5ff]/15 text-[#00e5ff] border border-[#00e5ff]/30 hover:bg-[#00e5ff]/25 text-sm font-bold transition-colors w-fit"
          >
            <Plus size={16} />
            {t('schedules.newProgram')}
          </button>
        )}
      </div>

      {/* Advisor suggestions if present */}
      {suggestions.filter((s) => s.status === 'pending' || s.status === 'approved').length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-[#bac9cc]">
            <AiSparklesIcon size={16} accent="#00e5ff" />
            <span>{t('advisor.title')}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestions
              .filter((s) => s.status === 'pending' || s.status === 'approved')
              .map((sug) => (
                <SuggestionCard
                  key={sug.id}
                  suggestion={sug}
                  onStatusChange={(updated) =>
                    setSuggestions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
                  }
                />
              ))}
          </div>
        </div>
      )}

      {/* 24-Hour Weekly Timeline Bar */}
      <div className="panel p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#bac9cc] flex items-center gap-1.5">
            <Calendar size={14} className="text-[#00e5ff]" />
            {t('schedules.timeline')}
          </span>
          <span className="text-[11px] text-[#849396]">00:00 – 24:00 (Africa/Tripoli)</span>
        </div>

        {/* Timeline Header (Hours) */}
        <div className="grid grid-cols-[60px_1fr] sm:grid-cols-[80px_1fr] gap-2 items-center text-[10px] text-[#849396] font-mono border-b border-white/5 pb-1">
          <div />
          <div className="flex justify-between px-1" dir="ltr">
            <span>00:00</span>
            <span>04:00</span>
            <span>08:00</span>
            <span>12:00</span>
            <span>16:00</span>
            <span>20:00</span>
            <span>24:00</span>
          </div>
        </div>

        {/* 7 Days Tracks */}
        <div className="space-y-2">
          {DAYS.map((day) => {
            const dayPrograms = programs.filter((p) => parseDays(p.weekday_mask).includes(day.dayNum));

            return (
              <div key={day.dayNum} className="grid grid-cols-[60px_1fr] sm:grid-cols-[80px_1fr] gap-2 items-center">
                <span className="text-xs font-medium text-[#bac9cc] truncate">{t(day.key)}</span>
                <div className="h-8 bg-black/40 rounded-lg border border-white/5 relative overflow-hidden flex items-center px-0.5">
                  {/* Vertical hour marker lines */}
                  <div className="absolute inset-0 flex justify-between pointer-events-none opacity-10 px-1" dir="ltr">
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                    <div className="border-r border-white h-full" />
                  </div>

                  {/* Program blocks */}
                  {dayPrograms.map((p) => {
                    const [h, m] = p.start_time_local.split(':').map(Number);
                    const startMin = (h || 0) * 60 + (m || 0);
                    const totalDur = p.steps.reduce((acc, s) => acc + s.duration_min, 0);

                    const leftPct = (startMin / 1440) * 100;
                    const widthPct = Math.max(2, (totalDur / 1440) * 100);

                    const blockStyle = isRtl
                      ? { right: `${leftPct}%`, width: `${widthPct}%` }
                      : { left: `${leftPct}%`, width: `${widthPct}%` };

                    return (
                      <div
                        key={p.id}
                        onClick={() => openEditDrawer(p)}
                        style={blockStyle}
                        title={`${p.name} (${p.start_time_local}, ${totalDur} min)`}
                        className={`absolute h-6 rounded px-1.5 flex items-center text-[10px] font-bold truncate cursor-pointer transition-all border ${
                          p.enabled
                            ? 'bg-[#00e5ff]/20 border-[#00e5ff] text-[#00e5ff] hover:bg-[#00e5ff]/35'
                            : 'bg-white/10 border-white/20 text-[#849396] hover:bg-white/15'
                        }`}
                      >
                        <span className="truncate">{p.name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Programs List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[#bac9cc]">{t('schedules.list')}</h2>
          <span className="text-xs text-[#849396] font-mono">{programs.length} programs</span>
        </div>

        {loading ? (
          <div className="panel p-8 text-center text-sm text-[#849396]">{t('common.loading')}</div>
        ) : programs.length === 0 ? (
          <div className="panel p-8 text-center space-y-2">
            <div className="text-sm font-bold text-[#bac9cc]">{t('schedules.noPrograms')}</div>
            <p className="text-xs text-[#849396] max-w-sm mx-auto">{t('schedules.noProgramsHint')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {programs.map((p) => {
              const totalDur = p.steps.reduce((acc, s) => acc + s.duration_min, 0);
              const activeDays = parseDays(p.weekday_mask);

              return (
                <div
                  key={p.id}
                  className={`panel p-4 space-y-3 transition-colors ${
                    p.enabled ? 'border-white/15' : 'border-white/5 opacity-70'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-base font-bold text-[#e5e2e1]">{p.name}</div>
                      <div className="flex items-center gap-2 text-xs text-[#849396] mt-0.5 font-mono">
                        <Clock size={13} className="text-[#00e5ff]" />
                        <span>{p.start_time_local}</span>
                        <span>•</span>
                        <span>{totalDur} min</span>
                        <span>•</span>
                        <span>{p.steps.length} zones</span>
                      </div>
                    </div>

                    {/* Enable Toggle Switch */}
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleToggle(p)}
                        disabled={!canToggle}
                        title={p.enabled ? t('schedules.enabled') : t('schedules.disabled')}
                        className={`w-11 h-6 rounded-full transition-colors relative p-0.5 ${
                          p.enabled ? 'bg-[#00e5ff]' : 'bg-white/20'
                        } ${!canToggle ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full bg-black transition-transform ${
                            p.enabled
                              ? isRtl
                                ? '-translate-x-5'
                                : 'translate-x-5'
                              : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Days Chips */}
                  <div className="flex gap-1">
                    {DAYS.map((d) => {
                      const active = activeDays.includes(d.dayNum);
                      return (
                        <span
                          key={d.dayNum}
                          className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold ${
                            active
                              ? 'bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/30'
                              : 'bg-white/5 text-[#849396] border border-white/5'
                          }`}
                        >
                          {t(d.key)[0]}
                        </span>
                      );
                    })}
                  </div>

                  {/* Steps sequence chips */}
                  <div className="flex flex-wrap gap-1.5 pt-1 border-t border-white/5">
                    {p.steps.map((st, idx) => {
                      const seed = SEED[st.zone_id];
                      const Crop = seed ? CROP_ICON[seed.crop_type] : null;
                      const zName = seed ? pickName(lang, seed.name, seed.name_ar) : st.zone_id;

                      return (
                        <div
                          key={st.id || idx}
                          className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-black/40 border border-white/5 text-xs"
                        >
                          {Crop && <Crop size={13} />}
                          <span className="text-[#bac9cc] truncate max-w-[120px]">{zName}</span>
                          <span className="text-[10px] text-[#00e5ff] font-mono">{st.duration_min}m</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Admin Edit/Delete */}
                  {isAdmin && (
                    <div className="flex justify-end gap-2 pt-2 border-t border-white/5">
                      <button
                        onClick={() => openEditDrawer(p)}
                        className="p-1.5 rounded-lg text-[#bac9cc] hover:text-[#00e5ff] hover:bg-white/5 text-xs flex items-center gap-1"
                      >
                        <Edit2 size={13} />
                        <span>Edit</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Program Edit / Create Drawer */}
      {isDrawerOpen && (
        <ProgramDrawer
          program={selectedProgram}
          onClose={() => setIsDrawerOpen(false)}
          onSaved={() => {
            setIsDrawerOpen(false);
            refreshPrograms();
          }}
          onDeleted={() => {
            setIsDrawerOpen(false);
            refreshPrograms();
          }}
        />
      )}
    </div>
  );
}

// ── Program Create / Edit Drawer ──────────────────────────────────────────────

interface DrawerProps {
  program: Program | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

function ProgramDrawer({ program, onClose, onSaved, onDeleted }: DrawerProps) {
  const { t, lang } = useT();
  const [name, setName] = useState(program?.name ?? '');
  const [startTime, setStartTime] = useState(program?.start_time_local ?? '06:00');
  const [selectedDays, setSelectedDays] = useState<number[]>(parseDays(program?.weekday_mask));
  const [steps, setSteps] = useState<StepDraft[]>(
    program?.steps?.map((s) => ({ zone_id: s.zone_id, duration_min: s.duration_min })) ?? [
      { zone_id: ZONE_SEEDS[0].id, duration_min: 30 },
    ]
  );

  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [conflict, setConflict] = useState<ConflictError | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Live conflict checking
  useEffect(() => {
    let active = true;
    if (steps.length === 0 || !startTime) return;

    const check = async () => {
      try {
        const payload: ProgramCreate = {
          name: name || 'Draft',
          start_time_local: startTime,
          weekday_mask: formatDays(selectedDays),
          steps: steps.map((s, idx) => ({ ...s, step_order: idx + 1 })),
        };
        const res = await apiFetch<{ ok: boolean; conflict?: ConflictError }>(
          '/api/v1/schedules/check-conflicts',
          {
            method: 'POST',
            body: JSON.stringify({ program: payload, exclude_program_id: program?.id }),
          }
        );
        if (active) {
          setConflict(res.conflict ?? null);
        }
      } catch {
        // If conflict check endpoint not available or returned error
      }
    };

    const timer = setTimeout(check, 350);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [name, startTime, selectedDays, steps, program?.id]);

  const toggleDay = (dayNum: number) => {
    setSelectedDays((prev) =>
      prev.includes(dayNum) ? prev.filter((d) => d !== dayNum) : [...prev, dayNum]
    );
  };

  const addStep = () => {
    const defaultZone = ZONE_SEEDS[steps.length % ZONE_SEEDS.length].id;
    setSteps((prev) => [...prev, { zone_id: defaultZone, duration_min: 30 }]);
  };

  const removeStep = (idx: number) => {
    setSteps((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateStepZone = (idx: number, zone_id: string) => {
    setSteps((prev) =>
      prev.map((s, i) => {
        if (i !== idx) return s;
        const seed = SEED[zone_id];
        const maxDur = seed?.max_runtime_min ?? 120;
        return { zone_id, duration_min: Math.min(s.duration_min, maxDur) };
      })
    );
  };

  const updateStepDuration = (idx: number, dur: number) => {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, duration_min: dur } : s)));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      alert(t('schedules.name'));
      return;
    }
    if (steps.length === 0) {
      alert(t('schedules.noSteps'));
      return;
    }

    setSaving(true);
    try {
      const payload: ProgramCreate = {
        name,
        start_time_local: startTime,
        weekday_mask: formatDays(selectedDays),
        steps: steps.map((s, idx) => ({ ...s, step_order: idx + 1 })),
      };

      if (program) {
        await apiFetch(`/api/v1/schedules/${program.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch('/api/v1/schedules', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }
      onSaved();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!program) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/schedules/${program.id}`, {
        method: 'DELETE',
      });
      onDeleted();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  const totalDuration = steps.reduce((sum, s) => sum + s.duration_min, 0);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs" onClick={onClose} />
      <div className="fixed inset-y-0 end-0 z-50 w-full max-w-lg bg-[#161618] border-s border-white/10 flex flex-col shadow-2xl">
        {/* Drawer Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-base font-bold text-[#e5e2e1]">
            {program ? t('schedules.drawerEdit') : t('schedules.drawerCreate')}
          </h2>
          <button onClick={onClose} className="p-1 text-[#849396] hover:text-[#e5e2e1]">
            ✕
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Program Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-[#bac9cc]">{t('schedules.name')}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('schedules.namePlaceholder')}
              className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-[#e5e2e1] focus:border-[#00e5ff] focus:outline-none"
            />
          </div>

          {/* Start Time & Total Duration */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#bac9cc]">{t('schedules.startTime')}</label>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-[#e5e2e1] font-mono focus:border-[#00e5ff] focus:outline-none"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#bac9cc]">{t('schedules.totalDuration')}</label>
              <div className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/5 text-sm font-mono text-[#00e5ff]">
                {totalDuration} min
              </div>
            </div>
          </div>

          {/* Days selector */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-[#bac9cc]">{t('schedules.days')}</label>
            <div className="grid grid-cols-7 gap-1">
              {DAYS.map((d) => {
                const active = selectedDays.includes(d.dayNum);
                return (
                  <button
                    key={d.dayNum}
                    type="button"
                    onClick={() => toggleDay(d.dayNum)}
                    className={`py-2 rounded-lg text-xs font-bold transition-all border ${
                      active
                        ? 'bg-[#00e5ff]/20 text-[#00e5ff] border-[#00e5ff]/50'
                        : 'bg-white/5 text-[#849396] border-white/5 hover:bg-white/10'
                    }`}
                  >
                    {t(d.key)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Conflict Banner */}
          {conflict && (
            <div className="p-3 rounded-xl bg-[#ff5449]/15 border border-[#ff5449]/30 text-xs text-[#ff5449] space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <AlertTriangle size={15} />
                <span>{t('schedules.conflictTitle')}</span>
              </div>
              <p>{lang === 'ar' ? conflict.message_ar : conflict.message_en}</p>
            </div>
          )}

          {/* Sequential Steps */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#bac9cc]">{t('schedules.steps')}</label>
              <button
                type="button"
                onClick={addStep}
                className="text-xs font-bold text-[#00e5ff] hover:underline flex items-center gap-1"
              >
                {t('schedules.addStep')}
              </button>
            </div>

            <div className="space-y-3">
              {steps.map((step, idx) => {
                const zoneSeed = SEED[step.zone_id];
                const maxDur = zoneSeed?.max_runtime_min ?? 120;
                const Crop = zoneSeed ? CROP_ICON[zoneSeed.crop_type] : null;

                return (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-black/40 border border-white/10 space-y-3 relative group"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="w-5 h-5 rounded-full bg-white/10 text-[11px] font-mono font-bold flex items-center justify-center text-[#849396]">
                        {idx + 1}
                      </span>

                      {/* Zone Selector */}
                      <div className="flex-1 min-w-0 flex items-center gap-2">
                        {Crop && <Crop size={16} />}
                        <select
                          value={step.zone_id}
                          onChange={(e) => updateStepZone(idx, e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-[#1e1e20] border border-white/10 text-xs text-[#e5e2e1] focus:border-[#00e5ff] focus:outline-none"
                        >
                          {ZONE_SEEDS.map((z) => (
                            <option key={z.id} value={z.id}>
                              {pickName(lang, z.name, z.name_ar)} ({t(('crop.' + z.crop_type) as MsgKey)}, max {z.max_runtime_min}m)
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Delete Step */}
                      {steps.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeStep(idx)}
                          className="p-1 text-[#849396] hover:text-[#ff5449]"
                          title="Remove step"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>

                    {/* Duration chips + slider */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[#849396]">{t('schedules.duration')}</span>
                        <span className="font-mono font-bold text-[#00e5ff]">
                          {step.duration_min} min (max {maxDur}m)
                        </span>
                      </div>

                      <div className="flex gap-1.5">
                        {PRESETS.filter((p) => p <= maxDur).map((p) => (
                          <button
                            key={p}
                            type="button"
                            onClick={() => updateStepDuration(idx, p)}
                            className={`flex-1 py-1 rounded text-xs font-mono font-bold transition-all ${
                              step.duration_min === p
                                ? 'bg-[#00e5ff] text-black'
                                : 'bg-white/5 text-[#bac9cc] hover:bg-white/10'
                            }`}
                          >
                            {p}m
                          </button>
                        ))}
                      </div>

                      <input
                        type="range"
                        min={5}
                        max={maxDur}
                        step={5}
                        value={step.duration_min}
                        onChange={(e) => updateStepDuration(idx, Number(e.target.value))}
                        className="w-full accent-[#00e5ff] cursor-pointer"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-4 border-t border-white/10 flex items-center justify-between gap-3 bg-[#141416]">
          {program ? (
            confirmDelete ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="px-3 py-1.5 rounded-lg bg-[#ff5449] text-white text-xs font-bold"
                >
                  {t('schedules.confirmDelete')}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="px-2 py-1.5 text-xs text-[#849396]"
                >
                  {t('schedules.cancel')}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="text-xs text-[#ff5449] hover:underline"
              >
                {t('schedules.delete')}
              </button>
            )
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-white/5 text-sm text-[#849396] hover:bg-white/10"
            >
              {t('schedules.cancel')}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 rounded-xl bg-[#00e5ff] text-black text-sm font-bold hover:brightness-110 flex items-center gap-1.5"
            >
              <Check size={16} />
              {saving ? t('common.loading') : t('schedules.save')}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
