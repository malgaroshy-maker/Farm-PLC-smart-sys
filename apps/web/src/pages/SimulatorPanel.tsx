import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { FlaskConical, Play, Square, Wrench } from 'lucide-react';
import type { ScenarioInfo, ScenarioRun, SystemMode } from '@algaroshy/contracts';
import { apiFetch } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useFarmStore } from '../store/farm';
import { useT, type MsgKey } from '../lib/i18n';
import { usePresenter } from '../lib/presenter';

interface FaultButton {
  label: string;
  ar: string;
  target_type: string;
  target_id?: string;
  fault_type: string;
  value?: number;
  danger?: boolean;
}

const FAULT_GROUPS: { title: MsgKey; faults: FaultButton[] }[] = [
  {
    title: 'sim.pumps',
    faults: [
      { label: 'Trip booster', ar: 'فصل مضخة التعزيز', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'trip', danger: true },
      { label: 'Booster fails to start', ar: 'فشل تشغيل التعزيز', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'fail_start', danger: true },
      { label: 'Repair booster', ar: 'إصلاح مضخة التعزيز', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'clear' },
      { label: 'Trip well pump', ar: 'فصل مضخة البئر', target_type: 'pump', target_id: 'pump_well_01', fault_type: 'trip', danger: true },
      { label: 'Repair well pump', ar: 'إصلاح مضخة البئر', target_type: 'pump', target_id: 'pump_well_01', fault_type: 'clear' },
    ],
  },
  {
    title: 'sim.system',
    faults: [
      { label: 'Mainline leak', ar: 'تسريب في الخط الرئيسي', target_type: 'system', fault_type: 'mainline_leak', danger: true },
      { label: 'Fix leak', ar: 'إصلاح التسريب', target_type: 'system', fault_type: 'clear_leak' },
      { label: 'Press E-STOP', ar: 'ضغط إيقاف الطوارئ', target_type: 'system', fault_type: 'estop', danger: true },
      { label: 'Release E-STOP', ar: 'تحرير إيقاف الطوارئ', target_type: 'system', fault_type: 'estop_release' },
      { label: 'Tank sensor fault', ar: 'عطل حساس الخزان', target_type: 'sensor', target_id: 'sensor_tank_level', fault_type: 'tank_level_fault', danger: true },
      { label: 'Fix tank sensor', ar: 'إصلاح حساس الخزان', target_type: 'sensor', target_id: 'sensor_tank_level', fault_type: 'clear' },
      { label: 'Drop comms 45 s', ar: 'قطع الاتصال 45 ث', target_type: 'comms', fault_type: 'drop', value: 45, danger: true },
      { label: 'Repair everything', ar: 'إصلاح كل شيء', target_type: 'system', fault_type: 'clear_all' },
    ],
  },
];

const STATUS_COLOR: Record<ScenarioRun['status'], string> = {
  idle: '#849396',
  running: '#00e5ff',
  passed: '#7ee787',
  failed: '#ffb4ab',
  stopped: '#ffeb3b',
};

export default function SimulatorPanel() {
  const { can } = useAuth();
  const { t, lang } = useT();
  const presenter = usePresenter((s) => s.on);
  const isAdmin = can('owner_admin');
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [initialRun, setInitialRun] = useState<ScenarioRun | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const liveRun = useFarmStore((s) => s.scenario);
  const state = useFarmStore((s) => s.state);
  const sendCommand = useFarmStore((s) => s.sendCommand);
  const run = liveRun ?? initialRun;
  const busy = run?.status === 'running';

  useEffect(() => {
    apiFetch<{ scenarios: ScenarioInfo[]; run: ScenarioRun }>('/api/v1/sim/scenarios')
      .then((r) => {
        setScenarios(r.scenarios);
        setInitialRun(r.run);
      })
      .catch(() => setMsg(t('sim.unavailable')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (text: string) => {
    setMsg(text);
    setTimeout(() => setMsg(null), 4000);
  };

  const runScenario = async (name: string) => {
    try {
      setInitialRun(await apiFetch<ScenarioRun>(`/api/v1/sim/scenarios/${name}/run`, { method: 'POST' }));
    } catch (e) {
      flash(e instanceof Error ? e.message : 'Could not start scenario');
    }
  };

  const stopScenario = async () => {
    await apiFetch<ScenarioRun>('/api/v1/sim/scenarios/stop', { method: 'POST' }).catch(() => null);
  };

  const inject = async (f: FaultButton) => {
    const res = await sendCommand({
      command_type: 'inject_fault',
      target_type: 'simulator',
      payload: { target_type: f.target_type, target_id: f.target_id ?? null, fault_type: f.fault_type, value: f.value ?? null },
    });
    flash(res.ok ? `${t('sim.sent')}: ${lang === 'ar' ? f.ar : f.label}` : `${t('sim.failed')}: ${res.message}`);
  };

  const setMode = async (mode: SystemMode) => {
    const res = await sendCommand({ command_type: 'set_mode', target_type: 'system', payload: { mode } });
    flash(res.ok ? `${t('sim.mode')} → ${t(`mode.${mode}` as MsgKey)}` : `${t('sim.failed')}: ${res.message}`);
  };

  const [tank, setTank] = useState(50);
  const setTankLevel = () =>
    inject({ label: `Tank → ${tank}%`, ar: `الخزان ← ${tank}%`, target_type: 'tank', fault_type: 'set_level', value: tank });

  if (!isAdmin || !presenter) return <Navigate to="/" replace />;

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#e5e2e1] flex items-center gap-3">
            <FlaskConical className="text-[#00e5ff]" size={26} /> {t('sim.title')}
          </h1>
          <p className="text-[#849396] mt-1 text-sm">{t('sim.subtitle')}</p>
        </div>
        {msg && <span className="font-mono text-xs text-[#ffeb3b]" role="status">{msg}</span>}
      </div>

      {/* Current run */}
      {run && run.name && (
        <div className="panel p-4 space-y-3">
          <div className="flex justify-between items-center font-mono text-sm">
            <span>
              <span style={{ color: STATUS_COLOR[run.status] }} className="font-bold me-3">{t(`sim.st.${run.status}` as MsgKey)}</span>
              <span dir="ltr">{run.name} · {t('sim.step')} {run.step}/{run.total}</span>
            </span>
            {busy && isAdmin && (
              <button onClick={stopScenario} className="flex items-center gap-2 px-3 py-1.5 border border-[#ffb4ab] text-[#ffb4ab] rounded text-xs">
                <Square size={14} /> {t('sim.stop')}
              </button>
            )}
          </div>
          <div className="h-1.5 bg-[#353534] rounded overflow-hidden">
            <div className="h-full transition-all" style={{ width: `${run.total ? (run.step / run.total) * 100 : 0}%`, backgroundColor: STATUS_COLOR[run.status] }} />
          </div>
          <pre className="text-xs text-[#bac9cc] font-mono max-h-40 overflow-y-auto whitespace-pre-wrap" dir="ltr">{run.log.slice(-12).join('\n')}</pre>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Scenarios */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-bold text-[#bac9cc]">{t('sim.scenarios')}</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {scenarios.map((s) => (
              <div key={s.name} className="panel p-4 flex flex-col gap-2">
                <div className="flex justify-between gap-2">
                  <div>
                    <div className="font-bold text-[#e5e2e1]">{lang === 'ar' ? s.title_ar : s.title}</div>
                    <div className="text-xs text-[#849396]">{lang === 'ar' ? s.title : s.title_ar}</div>
                  </div>
                  {isAdmin && (
                    <button
                      disabled={busy}
                      onClick={() => runScenario(s.name)}
                      aria-label={`Run ${s.title}`}
                      className="self-start p-2 rounded border border-[#353534] text-[#00e5ff] hover:border-[#00e5ff] disabled:opacity-40"
                    >
                      <Play size={16} />
                    </button>
                  )}
                </div>
                <p className="text-xs text-[#849396]">{s.description}</p>
                {s.expect.length > 0 && (
                  <p className="text-[10px] font-mono text-[#ffeb3b]" dir="ltr">{t('sim.expects')} {s.expect.join(' · ')}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Manual controls */}
        <div className="space-y-4">
          <div className="panel p-4 space-y-3">
            <h2 className="text-sm font-bold text-[#bac9cc]">{t('sim.mode')}</h2>
            <div className="grid grid-cols-2 gap-2">
              {(['auto', 'manual', 'maintenance', 'off'] as SystemMode[]).map((m) => (
                <button
                  key={m}
                  disabled={!isAdmin}
                  onClick={() => setMode(m)}
                  className={`py-2 rounded border text-xs disabled:opacity-40 ${state?.system_mode === m ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff]/10' : 'border-[#353534] text-[#bac9cc]'}`}
                >
                  {t(`mode.${m}` as MsgKey)}
                </button>
              ))}
            </div>
            <h2 className="text-sm font-bold text-[#bac9cc] pt-2">{t('sim.tank')}</h2>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={100}
                value={tank}
                onChange={(e) => setTank(Number(e.target.value))}
                className="flex-1 accent-[#00e5ff]"
                aria-label="Tank level to set"
              />
              <span className="font-mono text-sm w-10 text-end" dir="ltr">{tank}%</span>
              <button disabled={!isAdmin} onClick={setTankLevel} className="px-3 py-1.5 border border-[#353534] rounded text-xs disabled:opacity-40">
                {t('sim.set')}
              </button>
            </div>
          </div>

          {FAULT_GROUPS.map((g) => (
            <div key={g.title} className="panel p-4 space-y-2">
              <h2 className="text-sm font-bold text-[#bac9cc] flex items-center gap-2">
                <Wrench size={14} /> {t(g.title)}
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {g.faults.map((f) => (
                  <button
                    key={f.label}
                    disabled={!isAdmin}
                    onClick={() => inject(f)}
                    className={`py-2 px-2 rounded border text-[11px] text-start disabled:opacity-40 ${f.danger ? 'border-[#ffb4ab]/40 text-[#ffb4ab] hover:bg-[#ffb4ab]/10' : 'border-[#353534] text-[#7ee787] hover:bg-[#7ee787]/10'}`}
                  >
                    {lang === 'ar' ? f.ar : f.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
