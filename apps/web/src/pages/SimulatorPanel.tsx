import { useEffect, useState } from 'react';
import { FlaskConical, Play, Square, Wrench } from 'lucide-react';
import type { ScenarioInfo, ScenarioRun, SystemMode } from '@algaroshy/contracts';
import { apiFetch } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useFarmStore } from '../store/farm';

interface FaultButton {
  label: string;
  target_type: string;
  target_id?: string;
  fault_type: string;
  value?: number;
  danger?: boolean;
}

const FAULT_GROUPS: { title: string; faults: FaultButton[] }[] = [
  {
    title: 'PUMPS',
    faults: [
      { label: 'Trip booster', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'trip', danger: true },
      { label: 'Booster fails to start', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'fail_start', danger: true },
      { label: 'Repair booster', target_type: 'pump', target_id: 'pump_booster_01', fault_type: 'clear' },
      { label: 'Trip well pump', target_type: 'pump', target_id: 'pump_well_01', fault_type: 'trip', danger: true },
      { label: 'Repair well pump', target_type: 'pump', target_id: 'pump_well_01', fault_type: 'clear' },
    ],
  },
  {
    title: 'SYSTEM',
    faults: [
      { label: 'Mainline leak', target_type: 'system', fault_type: 'mainline_leak', danger: true },
      { label: 'Fix leak', target_type: 'system', fault_type: 'clear_leak' },
      { label: 'Press E-STOP', target_type: 'system', fault_type: 'estop', danger: true },
      { label: 'Release E-STOP', target_type: 'system', fault_type: 'estop_release' },
      { label: 'Tank sensor fault', target_type: 'sensor', target_id: 'sensor_tank_level', fault_type: 'tank_level_fault', danger: true },
      { label: 'Fix tank sensor', target_type: 'sensor', target_id: 'sensor_tank_level', fault_type: 'clear' },
      { label: 'Drop comms 45 s', target_type: 'comms', fault_type: 'drop', value: 45, danger: true },
      { label: 'Repair everything', target_type: 'system', fault_type: 'clear_all' },
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
      .catch(() => setMsg('Simulation controls unavailable (not in simulation mode?)'));
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
    flash(res.ok ? `Sent: ${f.label}` : `Failed: ${res.message}`);
  };

  const setMode = async (mode: SystemMode) => {
    const res = await sendCommand({ command_type: 'set_mode', target_type: 'system', payload: { mode } });
    flash(res.ok ? `Mode → ${mode}` : `Failed: ${res.message}`);
  };

  const [tank, setTank] = useState(50);
  const setTankLevel = () =>
    inject({ label: `Tank → ${tank}%`, target_type: 'tank', fault_type: 'set_level', value: tank });

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1] tracking-wider flex items-center gap-3 font-mono">
            <FlaskConical className="text-[#00e5ff]" size={28} /> SIMULATOR
          </h1>
          <p className="text-[#849396] mt-1 font-mono text-sm">
            SCENARIOS & FAULT INJECTION — SIMULATION MODE ONLY
            {!isAdmin && ' · VIEW ONLY (admin required)'}
          </p>
        </div>
        {msg && <span className="font-mono text-xs text-[#ffeb3b]" role="status">{msg}</span>}
      </div>

      {/* Current run */}
      {run && run.name && (
        <div className="bg-[#1c1b1b] border border-[#353534] rounded-lg p-4 space-y-3">
          <div className="flex justify-between items-center font-mono text-sm">
            <span>
              <span style={{ color: STATUS_COLOR[run.status] }} className="font-bold mr-3">{run.status.toUpperCase()}</span>
              {run.name} · step {run.step}/{run.total}
            </span>
            {busy && isAdmin && (
              <button onClick={stopScenario} className="flex items-center gap-2 px-3 py-1.5 border border-[#ffb4ab] text-[#ffb4ab] rounded text-xs">
                <Square size={14} /> STOP
              </button>
            )}
          </div>
          <div className="h-1.5 bg-[#353534] rounded overflow-hidden">
            <div className="h-full transition-all" style={{ width: `${run.total ? (run.step / run.total) * 100 : 0}%`, backgroundColor: STATUS_COLOR[run.status] }} />
          </div>
          <pre className="text-xs text-[#bac9cc] font-mono max-h-40 overflow-y-auto whitespace-pre-wrap">{run.log.slice(-12).join('\n')}</pre>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Scenarios */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-xs font-bold font-mono tracking-widest text-[#bac9cc]">SCENARIOS</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {scenarios.map((s) => (
              <div key={s.name} className="bg-[#1c1b1b] border border-[#353534] rounded-lg p-4 flex flex-col gap-2">
                <div className="flex justify-between gap-2">
                  <div>
                    <div className="font-bold text-[#e5e2e1]">{s.title}</div>
                    <div className="text-xs text-[#bac9cc]" dir="rtl">{s.title_ar}</div>
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
                  <p className="text-[10px] font-mono text-[#ffeb3b]">EXPECTS {s.expect.join(' · ')}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Manual controls */}
        <div className="space-y-4">
          <div className="bg-[#1c1b1b] border border-[#353534] rounded-lg p-4 space-y-3">
            <h2 className="text-xs font-bold font-mono tracking-widest text-[#bac9cc]">SYSTEM MODE</h2>
            <div className="grid grid-cols-2 gap-2">
              {(['auto', 'manual', 'maintenance', 'off'] as SystemMode[]).map((m) => (
                <button
                  key={m}
                  disabled={!isAdmin}
                  onClick={() => setMode(m)}
                  className={`py-2 rounded border font-mono text-xs uppercase disabled:opacity-40 ${state?.system_mode === m ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff]/10' : 'border-[#353534] text-[#bac9cc]'}`}
                >
                  {m}
                </button>
              ))}
            </div>
            <h2 className="text-xs font-bold font-mono tracking-widest text-[#bac9cc] pt-2">TANK LEVEL</h2>
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
              <span className="font-mono text-sm w-10 text-right">{tank}%</span>
              <button disabled={!isAdmin} onClick={setTankLevel} className="px-3 py-1.5 border border-[#353534] rounded font-mono text-xs disabled:opacity-40">
                SET
              </button>
            </div>
          </div>

          {FAULT_GROUPS.map((g) => (
            <div key={g.title} className="bg-[#1c1b1b] border border-[#353534] rounded-lg p-4 space-y-2">
              <h2 className="text-xs font-bold font-mono tracking-widest text-[#bac9cc] flex items-center gap-2">
                <Wrench size={14} /> {g.title}
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {g.faults.map((f) => (
                  <button
                    key={f.label}
                    disabled={!isAdmin}
                    onClick={() => inject(f)}
                    className={`py-2 px-2 rounded border font-mono text-[11px] text-left disabled:opacity-40 ${f.danger ? 'border-[#ffb4ab]/40 text-[#ffb4ab] hover:bg-[#ffb4ab]/10' : 'border-[#353534] text-[#7ee787] hover:bg-[#7ee787]/10'}`}
                  >
                    {f.label}
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
