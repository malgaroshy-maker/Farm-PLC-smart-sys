import { memo, useEffect, useMemo, useState } from 'react';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';
import { Maximize, Moon, Sun, SunMoon, ZoomIn, ZoomOut } from 'lucide-react';
import type { FarmMapState, PumpLiveState, ValveLiveState, ZoneLiveState } from '@algaroshy/contracts';
import { FARM, polygonPath, polylinePath, type Point } from '@algaroshy/map-model';
import { EQUIPMENT_SIZE, SPRITES, TEXTURES, TRUNK_LENGTH, TRUNK_PARENT, ZONES, type ZoneLayout } from './farmLayout';
import { fmtNum, pickName, useT, type MsgKey } from '../../lib/i18n';

type Light = 'auto' | 'day' | 'night';
type UiState = 'running' | 'busy' | 'fault' | 'idle';

const TRANSITIONAL = new Set(['queued', 'starting_pump', 'opening_valve', 'validating_flow', 'stopping']);
const [VX, VY, VW, VH] = FARM.viewBox;

function uiState(z?: ZoneLiveState): UiState {
  if (!z) return 'idle';
  if (z.state === 'faulted' || z.health === 'critical') return 'fault';
  if (z.state === 'running') return 'running';
  if (TRANSITIONAL.has(z.state)) return 'busy';
  return 'idle';
}

const STATE_STROKE: Record<UiState, string> = {
  running: '#00e5ff',
  busy: '#ffeb3b',
  fault: '#ff5449',
  idle: 'rgba(229,226,225,0.35)',
};

/** Farm-local hour (Africa/Tripoli) as a float. */
function farmHour(now: Date): number {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Tripoli',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now);
  const h = Number(parts.find((p) => p.type === 'hour')?.value ?? 12);
  const m = Number(parts.find((p) => p.type === 'minute')?.value ?? 0);
  return h + m / 60;
}

/** 0 = full day, 1 = full night; plus a warm tint around sunrise/sunset. */
function lighting(mode: Light, hour: number): { night: number; dusk: number } {
  if (mode === 'day') return { night: 0, dusk: 0 };
  if (mode === 'night') return { night: 1, dusk: 0 };
  const sun = Math.sin((Math.PI * (hour - 6)) / 12); // >0 between 06:00 and 18:00
  const night = sun >= 0.15 ? 0 : Math.min(1, (0.15 - sun) / 0.45);
  const dusk = sun > -0.2 && sun < 0.3 ? 1 - Math.abs(sun - 0.05) / 0.25 : 0;
  return { night, dusk: Math.max(0, dusk) };
}

function useFarmClock(): number {
  const [hour, setHour] = useState(() => farmHour(new Date()));
  useEffect(() => {
    const id = setInterval(() => setHour(farmHour(new Date())), 60_000);
    return () => clearInterval(id);
  }, []);
  return hour;
}

// ── Static layers (never re-render on telemetry) ─────────────────────────

const Defs = memo(function Defs() {
  return (
    <defs>
      {(['sand', 'track'] as const).map((k) => (
        <pattern key={k} id={`tex-${k}`} patternUnits="userSpaceOnUse" width={TEXTURES[k].w} height={TEXTURES[k].h}>
          <image href={TEXTURES[k].href} width={TEXTURES[k].w} height={TEXTURES[k].h} preserveAspectRatio="none" />
        </pattern>
      ))}
      {ZONES.map((z) => {
        const t = TEXTURES[z.crop];
        return (
          <pattern
            key={z.id}
            id={`crop-${z.id}`}
            patternUnits="userSpaceOnUse"
            width={t.w}
            height={t.h}
            patternTransform={`rotate(${z.angle + 90})`}
          >
            <image href={t.href} width={t.w} height={t.h} preserveAspectRatio="none" />
          </pattern>
        );
      })}
      {/* drip wet spots: dark damp soil blooming under each tree while irrigating */}
      <radialGradient id="wet-spot">
        <stop offset="0%" stopColor="#1b120a" stopOpacity="0.75" />
        <stop offset="70%" stopColor="#2a1b0e" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#2a1b0e" stopOpacity="0" />
      </radialGradient>
      {ZONES.map((z) => {
        const t = TEXTURES[z.crop];
        const step = t.w / 4;
        return (
          <pattern
            key={`wet-${z.id}`}
            id={`wet-${z.id}`}
            patternUnits="userSpaceOnUse"
            width={step}
            height={step}
            patternTransform={`rotate(${z.angle + 90})`}
          >
            <circle cx={step / 2} cy={step / 2} r={step * 0.48} fill="url(#wet-spot)" />
          </pattern>
        );
      })}
      <radialGradient id="lamp">
        <stop offset="0%" stopColor="#ffd27a" stopOpacity="0.85" />
        <stop offset="100%" stopColor="#ffd27a" stopOpacity="0" />
      </radialGradient>
      <filter id="label-shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="0" stdDeviation="1.2" floodColor="#000" floodOpacity="0.9" />
      </filter>
    </defs>
  );
});

const Ground = memo(function Ground() {
  const boundary = polygonPath(FARM.features.boundary.points);
  return (
    <g>
      <rect x={VX} y={VY} width={VW} height={VH} fill="url(#tex-sand)" />
      {/* outside the farm: darker desert */}
      <path d={`M${VX},${VY}H${VW}V${VH}H${VX}Z ${boundary}`} fillRule="evenodd" fill="#0e0e0e" fillOpacity={0.55} />
      <path d={boundary} fill="none" stroke="#e5e2e1" strokeOpacity={0.5} strokeWidth={1.6} strokeDasharray="6 4" />
      {FARM.tracks.map((t, i) => (
        <g key={i}>
          <path d={polylinePath(t)} fill="none" stroke="#5c4630" strokeOpacity={0.5} strokeWidth={11} strokeLinecap="round" strokeLinejoin="round" />
          <path d={polylinePath(t)} fill="none" stroke="url(#tex-track)" strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" />
        </g>
      ))}
    </g>
  );
});

// ── Dynamic layers ───────────────────────────────────────────────────────

function Zone({
  z,
  live,
  selected,
  onSelect,
}: {
  z: ZoneLayout;
  live?: ZoneLiveState;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const s = uiState(live);
  const d = polygonPath(z.points);
  const flowing = (live?.flow_m3h ?? 0) > 0.05;
  const moisture = live?.moisture_pct ?? 40;
  const stress = Math.max(0, Math.min(1, (28 - moisture) / 18)); // dry → yellowed canopy
  return (
    <g className="cursor-pointer" onClick={() => onSelect(z.id)} role="button" aria-label={z.name}>
      <path d={d} fill={`url(#crop-${z.id})`} />
      {stress > 0 && <path d={d} fill="#c9a227" fillOpacity={0.35 * stress} style={{ mixBlendMode: 'color' }} />}
      {flowing && (
        <g className="map-wet" pointerEvents="none">
          <path d={d} fill="#3a2410" fillOpacity={0.55} />
          <path d={d} fill={`url(#wet-${z.id})`} />
          <path d={d} fill="#00e5ff" fillOpacity={0.06} style={{ mixBlendMode: 'screen' }} />
        </g>
      )}
      <path
        d={d}
        fill={selected ? 'rgba(255,255,255,0.08)' : 'transparent'}
        stroke={selected ? '#ffffff' : STATE_STROKE[s]}
        strokeWidth={selected ? 2.6 : s === 'idle' ? 1 : 2.2}
        strokeDasharray={s === 'busy' ? '6 4' : undefined}
        strokeLinejoin="round"
        className={s === 'fault' ? 'map-fault' : s === 'running' ? 'map-glow' : undefined}
      />
    </g>
  );
}

function Pipes({ zones, pumps }: { zones: Record<string, ZoneLiveState>; pumps: Record<string, PumpLiveState> }) {
  const flowByTrunk: Record<string, number> = {};
  for (const z of ZONES) {
    const q = zones[z.id]?.flow_m3h ?? 0;
    if (q <= 0.05) continue;
    for (let t: string | undefined = z.trunk; t; t = TRUNK_PARENT[t]) flowByTrunk[t] = (flowByTrunk[t] ?? 0) + q;
  }
  const refill = pumps.pump_well_01?.state === 'running';
  return (
    <g fill="none" strokeLinecap="round" strokeLinejoin="round">
      {Object.entries(FARM.network.mainline).map(([name, pts]) => {
        const q = flowByTrunk[name] ?? 0;
        return (
          <g key={name}>
            <path d={polylinePath(pts)} stroke="#0d2a33" strokeWidth={3.4} />
            <path d={polylinePath(pts)} stroke="#2b6577" strokeWidth={1.8} />
            {q > 0 && (
              <path
                d={polylinePath(pts)}
                stroke="#00e5ff"
                strokeWidth={1.8}
                strokeDasharray="5 9"
                className="map-flow"
                style={{ animationDuration: `${Math.max(0.5, Math.min(4, 30 / q)) * (TRUNK_LENGTH[name] / 200)}s` }}
              />
            )}
          </g>
        );
      })}
      {ZONES.map((z) => {
        const v = FARM.network.valves[z.id];
        const q = zones[z.id]?.flow_m3h ?? 0;
        const d = polylinePath([v.tap, v.valve]);
        return (
          <g key={z.id}>
            <path d={d} stroke="#2b6577" strokeWidth={1.3} />
            {q > 0.05 && <path d={d} stroke="#00e5ff" strokeWidth={1.3} strokeDasharray="3 5" className="map-flow" style={{ animationDuration: '0.8s' }} />}
          </g>
        );
      })}
      <path d={polylinePath(FARM.network.refill)} stroke="#2b6577" strokeWidth={1.6} />
      {refill && (
        <path d={polylinePath(FARM.network.refill)} stroke="#7ee787" strokeWidth={1.6} strokeDasharray="3 5" className="map-flow" style={{ animationDuration: '1s' }} />
      )}
    </g>
  );
}

const VALVE_COLOR: Record<string, string> = { open: '#00e5ff', opening: '#ffeb3b', closing: '#ffeb3b', fault: '#ff5449' };

function Valves({ valves }: { valves: Record<string, ValveLiveState> }) {
  return (
    <g>
      {ZONES.map((z) => {
        const [x, y] = FARM.network.valves[z.id].valve;
        const v = Object.values(valves).find((vv) => vv.zone_id === z.id);
        const status = v?.status ?? 'closed';
        const open = status === 'open' || status === 'opening';
        return (
          <g key={z.id} transform={`translate(${x} ${y})`}>
            <rect x={-3.2} y={-3.2} width={6.4} height={6.4} rx={1} fill="#141414" stroke="#3b494c" strokeWidth={0.6} />
            {/* bow-tie valve symbol: rotates 90° as it opens */}
            <g className="map-valve" style={{ transform: `rotate(${open ? 90 : 0}deg)` }}>
              <path d="M-2.4,-1.6 L0,0 L-2.4,1.6Z M2.4,-1.6 L0,0 L2.4,1.6Z" fill={VALVE_COLOR[status] ?? '#849396'} />
            </g>
          </g>
        );
      })}
    </g>
  );
}

function Sprite({ href, at, size, label }: { href: string; at: Point; size: number; label: string }) {
  return (
    <image href={href} x={at[0] - size / 2} y={at[1] - size / 2} width={size} height={size} preserveAspectRatio="xMidYMid meet">
      <title>{label}</title>
    </image>
  );
}

function Equipment({
  pumps,
  tankPct,
  t,
}: {
  pumps: Record<string, PumpLiveState>;
  tankPct: number;
  t: (k: MsgKey) => string;
}) {
  const e = FARM.equipment;
  const booster = pumps.pump_booster_01;
  const well = pumps.pump_well_01;
  const rotor = (p: PumpLiveState | undefined, at: Point, r: number) => {
    const color = p?.fault || p?.state === 'failed_start' ? '#ff5449' : p?.state === 'running' ? '#00e5ff' : '#849396';
    return (
      <g transform={`translate(${at[0]} ${at[1]})`}>
        <circle r={r + 1.2} fill="#0e0e0e" fillOpacity={0.7} stroke={color} strokeWidth={0.8} />
        <g className={p?.state === 'running' ? 'map-spin' : undefined}>
          {[0, 120, 240].map((a) => (
            <path key={a} d={`M0,0 Q${r * 0.6},${-r * 0.4} ${r},0 Q${r * 0.6},${r * 0.2} 0,0`} fill={color} transform={`rotate(${a})`} />
          ))}
        </g>
      </g>
    );
  };
  const tank = e.tank.at;
  const gx = tank[0] - EQUIPMENT_SIZE.tank / 2 - 6;
  const gh = EQUIPMENT_SIZE.tank;
  const gy = tank[1] - gh / 2;
  const fill = Math.max(0, Math.min(100, tankPct)) / 100;
  const levelColor = tankPct < 10 ? '#ff5449' : tankPct < 25 ? '#ffeb3b' : '#00e5ff';
  return (
    <g>
      <Sprite href={SPRITES.wellhead} at={e.wellhead.at} size={EQUIPMENT_SIZE.wellhead} label={t('map.well')} />
      <Sprite href={SPRITES.control_room} at={e.well_room.at} size={EQUIPMENT_SIZE.control_room} label={t('map.well')} />
      <Sprite href={SPRITES.tank} at={tank} size={EQUIPMENT_SIZE.tank} label={t('map.tank')} />
      <Sprite href={SPRITES.booster} at={e.booster.at} size={EQUIPMENT_SIZE.booster} label={t('map.booster')} />
      {rotor(booster, [e.booster.at[0] + 5, e.booster.at[1] + 3], 2.6)}
      {rotor(well, [e.wellhead.at[0] - 6, e.wellhead.at[1] - 4], 2.2)}
      {/* tank level gauge (closed concrete roof: level comes from the sensor) */}
      <g>
        <rect x={gx - 2} y={gy} width={4} height={gh} rx={1} fill="#0e0e0e" stroke="#3b494c" strokeWidth={0.5} />
        <rect x={gx - 1.4} y={gy + gh * (1 - fill)} width={2.8} height={gh * fill} fill={levelColor} className="map-tank" />
        <text x={gx} y={gy - 2} textAnchor="middle" fontSize={5} direction="ltr" fill={levelColor} filter="url(#label-shadow)" fontFamily="IBM Plex Mono, monospace">
          {fmtNum(tankPct)}%
        </text>
      </g>
    </g>
  );
}

/** Work lights at the pump station and control room — drawn above the night overlay. */
function Lamps({ night }: { night: number }) {
  if (night < 0.3) return null;
  const e = FARM.equipment;
  return (
    <g pointerEvents="none" style={{ mixBlendMode: 'screen' }}>
      <circle cx={e.well_room.at[0]} cy={e.well_room.at[1]} r={28} fill="url(#lamp)" opacity={night * 0.8} />
      <circle cx={e.tank.at[0]} cy={e.tank.at[1]} r={24} fill="url(#lamp)" opacity={night * 0.55} />
    </g>
  );
}

function Labels({ zones, lang }: { zones: Record<string, ZoneLiveState>; lang: 'ar' | 'en' }) {
  return (
    <g pointerEvents="none" fontFamily="'IBM Plex Sans Arabic', 'IBM Plex Mono', sans-serif" textAnchor="middle">
      {ZONES.map((z) => {
        const live = zones[z.id];
        const s = uiState(live);
        const [x, y] = z.label;
        const fs = z.small ? 8 : 15;
        return (
          <g key={z.id} filter="url(#label-shadow)">
            <text x={x} y={y} fontSize={fs} fontWeight={700} fill="#ffffff">
              {pickName(lang, z.name, z.nameAr)}
            </text>
            {!z.small && (
              <text x={x} y={y + fs * 1.15} fontSize={fs * 0.7} direction="ltr" fill={STATE_STROKE[s] === STATE_STROKE.idle ? '#e5e2e1' : STATE_STROKE[s]} fontFamily="IBM Plex Mono, monospace">
                {fmtNum(live?.moisture_pct, 0)}%{s === 'running' && live?.flow_m3h ? ` · ${fmtNum(live.flow_m3h, 1)} m³/h` : ''}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

// ── Map ──────────────────────────────────────────────────────────────────

export default function FarmMap({
  state,
  selectedZone,
  onZoneSelect,
}: {
  state: FarmMapState | null;
  selectedZone: string | null;
  onZoneSelect: (id: string) => void;
}) {
  const { t, lang } = useT();
  const [light, setLight] = useState<Light>('auto');
  const hour = useFarmClock();
  const { night, dusk } = lighting(light, hour);

  const zones = useMemo(() => Object.fromEntries((state?.zones ?? []).map((z) => [z.zone_id, z])), [state?.zones]);
  const pumps = useMemo(() => Object.fromEntries((state?.pumps ?? []).map((p) => [p.pump_id, p])), [state?.pumps]);
  const valves = useMemo(() => Object.fromEntries((state?.valves ?? []).map((v) => [v.valve_id, v])), [state?.valves]);

  const lightModes: { mode: Light; icon: typeof Sun; key: MsgKey }[] = [
    { mode: 'auto', icon: SunMoon, key: 'map.light.auto' },
    { mode: 'day', icon: Sun, key: 'map.light.day' },
    { mode: 'night', icon: Moon, key: 'map.light.night' },
  ];

  return (
    <div className="w-full h-full bg-[#0e0e0e] border border-[#3b494c] rounded-xl overflow-hidden relative shadow-2xl">
      {/* legend */}
      <div className="absolute top-3 start-3 z-20 max-w-[calc(100%-8.5rem)] flex flex-wrap gap-x-3 gap-y-1 text-[11px] sm:text-xs bg-[#1c1b1b]/85 backdrop-blur border border-[#353534] px-2.5 py-1.5 rounded-lg pointer-events-none">
        {(['running', 'busy', 'fault', 'idle'] as UiState[]).map((s) => (
          <span key={s} className="flex items-center gap-1.5" style={{ color: s === 'idle' ? '#bac9cc' : STATE_STROKE[s] }}>
            <span className="w-2.5 h-2.5 rounded-sm border" style={{ borderColor: STATE_STROKE[s], background: s === 'idle' ? 'transparent' : `${STATE_STROKE[s]}33` }} />
            {t(`map.legend.${s}` as MsgKey)}
          </span>
        ))}
      </div>

      {/* lighting toggle */}
      <div className="absolute top-3 end-3 z-20 flex gap-1 bg-[#1c1b1b]/85 backdrop-blur border border-[#353534] p-1 rounded-lg">
        {lightModes.map(({ mode, icon: Icon, key }) => (
          <button
            key={mode}
            onClick={() => setLight(mode)}
            title={t(key)}
            aria-label={t(key)}
            aria-pressed={light === mode}
            className={`p-1.5 rounded ${light === mode ? 'bg-[#00e5ff]/15 text-[#00e5ff]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}
          >
            <Icon size={16} />
          </button>
        ))}
      </div>

      <TransformWrapper initialScale={1} minScale={0.8} maxScale={8} centerOnInit wheel={{ step: 0.15 }}>
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="absolute bottom-3 end-3 z-20 flex flex-col gap-2">
              {[
                { f: () => zoomIn(), I: ZoomIn, l: '+' },
                { f: () => zoomOut(), I: ZoomOut, l: '−' },
                { f: () => resetTransform(), I: Maximize, l: 'reset' },
              ].map(({ f, I, l }) => (
                <button key={l} onClick={f} aria-label={l} className="bg-[#201f1f]/85 backdrop-blur border border-[#353534] p-2 rounded text-[#e5e2e1] hover:bg-[#353534]">
                  <I size={18} />
                </button>
              ))}
            </div>
            <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full">
              <svg viewBox={`${VX} ${VY} ${VW} ${VH}`} className="w-full h-full block" role="img" aria-label={t('map.title')}>
                <Defs />
                <Ground />
                {ZONES.map((z) => (
                  <Zone key={z.id} z={z} live={zones[z.id]} selected={selectedZone === z.id} onSelect={onZoneSelect} />
                ))}
                <Pipes zones={zones} pumps={pumps} />
                <Valves valves={valves} />
                <Equipment pumps={pumps} tankPct={state?.tank_level_pct ?? 0} t={t} />
                {/* lighting: tints the world, then lamps and labels stay readable on top */}
                {dusk > 0 && <rect x={VX} y={VY} width={VW} height={VH} fill="#ff8a3d" opacity={dusk * 0.18} style={{ mixBlendMode: 'soft-light' }} pointerEvents="none" />}
                {night > 0 && <rect x={VX} y={VY} width={VW} height={VH} fill="#0a1430" opacity={night * 0.62} style={{ mixBlendMode: 'multiply' }} pointerEvents="none" />}
                <Lamps night={night} />
                <Labels zones={zones} lang={lang} />
              </svg>
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
