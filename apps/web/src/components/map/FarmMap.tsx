/**
 * Farm map — layered:
 *   SVG ground (sand, tracks, field soil) → WetCanvas → TreeCanvas →
 *   SVG overlay (zones, alarm rings, pipes, valves, equipment, farm life,
 *   focus dimming, lighting, lamps, label chips) + HTML tooltip & controls.
 * Camera flies to a selected zone and to the zone/equipment of a new major alarm.
 */
import { memo, useEffect, useMemo, useRef, useState } from 'react';
import { TransformComponent, TransformWrapper, type ReactZoomPanPinchContentRef } from 'react-zoom-pan-pinch';
import { Maximize, Moon, Sun, SunMoon, Undo2, ZoomIn, ZoomOut } from 'lucide-react';
import type { Alarm, AlarmSeverity, FarmMapState, PumpLiveState, ValveLiveState, ZoneLiveState } from '@algaroshy/contracts';
import { FARM, polygonPath, polylinePath, type Point } from '@algaroshy/map-model';
import { EQUIPMENT_SIZE, SPRITES, TEXTURES, TRUNK_LENGTH, TRUNK_PARENT, ZONES, type ZoneLayout } from './farmLayout';
import { TreeCanvas, WetCanvas } from './MapCanvases';
import FarmLife from './FarmLife';
import { fmtNum, pickName, useT, type MsgKey } from '../../lib/i18n';
import { SEVERITY, topSeverity } from '../../lib/alarms';
import { usePrefs } from '../../lib/prefs';
import { useFarmStore } from '../../store/farm';
import { useFarmClock } from '../../lib/clock';

type Light = 'auto' | 'day' | 'night';
type UiState = 'running' | 'busy' | 'fault' | 'idle';

const TRANSITIONAL = new Set(['queued', 'starting_pump', 'opening_valve', 'validating_flow', 'stopping']);
const [VX, VY, VW, VH] = FARM.viewBox;
const CYAN = '#00e5ff';

function uiState(z?: ZoneLiveState): UiState {
  if (!z) return 'idle';
  if (z.state === 'faulted' || z.health === 'critical') return 'fault';
  if (z.state === 'running') return 'running';
  if (TRANSITIONAL.has(z.state)) return 'busy';
  return 'idle';
}

const STATE_COLOR: Record<UiState, string> = {
  running: CYAN,
  busy: '#ffeb3b',
  fault: '#ff5449',
  idle: 'rgba(229,226,225,0.28)',
};

// ── time & light ─────────────────────────────────────────────────────────

function lighting(mode: Light, hour: number): { night: number; dusk: number } {
  if (mode === 'day') return { night: 0, dusk: 0 };
  if (mode === 'night') return { night: 1, dusk: 0 };
  const sun = Math.sin((Math.PI * (hour - 6)) / 12);
  const night = sun >= 0.15 ? 0 : Math.min(1, (0.15 - sun) / 0.45);
  const dusk = sun > -0.2 && sun < 0.3 ? 1 - Math.abs(sun - 0.05) / 0.25 : 0;
  return { night, dusk: Math.max(0, dusk) };
}

// ── alarm → map location ─────────────────────────────────────────────────

const EQUIPMENT_FOR_DEVICE: Record<string, 'booster' | 'wellhead' | 'tank'> = {
  pump_booster_01: 'booster',
  pump_well_01: 'wellhead',
  sensor_tank_level: 'tank',
};

function zoneOfAlarm(a: Pick<Alarm, 'zone_id' | 'device_id'>): string | null {
  if (a.zone_id) return a.zone_id;
  if (a.device_id?.startsWith('valve_')) return `zone_${a.device_id.slice(6)}`;
  return null;
}

// ── static layers ────────────────────────────────────────────────────────

const Ground = memo(function Ground() {
  const boundary = polygonPath(FARM.features.boundary.points);
  return (
    <svg viewBox={`${VX} ${VY} ${VW} ${VH}`} className="absolute inset-0 w-full h-full" aria-hidden="true">
      <defs>
        {(['sand', 'track'] as const).map((k) => (
          <pattern key={k} id={`tex-${k}`} patternUnits="userSpaceOnUse" width={TEXTURES[k].w} height={TEXTURES[k].h}>
            <image href={TEXTURES[k].href} width={TEXTURES[k].w} height={TEXTURES[k].h} preserveAspectRatio="none" />
          </pattern>
        ))}
      </defs>
      <rect x={VX} y={VY} width={VW} height={VH} fill="url(#tex-sand)" />
      {/* tilled field soil: slightly darker and warmer than bare sand */}
      {ZONES.map((z) => (
        <path key={z.id} d={polygonPath(z.points)} fill="#5a3a1c" fillOpacity={0.2} />
      ))}
      {FARM.tracks.map((t, i) => (
        <g key={i} fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d={polylinePath(t)} stroke="#3e2c1a" strokeOpacity={0.35} strokeWidth={12} />
          <path d={polylinePath(t)} stroke="url(#tex-track)" strokeWidth={9.5} />
        </g>
      ))}
      {/* outside the farm: darker desert */}
      <path d={`M${VX},${VY}H${VW}V${VH}H${VX}Z ${boundary}`} fillRule="evenodd" fill="#0e0e0e" fillOpacity={0.5} />
      <path d={boundary} fill="none" stroke="#e5e2e1" strokeOpacity={0.45} strokeWidth={1.4} strokeDasharray="6 4" />
    </svg>
  );
});

const OverlayDefs = memo(function OverlayDefs() {
  return (
    <defs>
      <radialGradient id="lamp">
        <stop offset="0%" stopColor="#ffd27a" stopOpacity="0.85" />
        <stop offset="100%" stopColor="#ffd27a" stopOpacity="0" />
      </radialGradient>
      <filter id="soft-shadow" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="1.2" dy="1.4" stdDeviation="1.2" floodColor="#000" floodOpacity="0.45" />
      </filter>
    </defs>
  );
});

// ── overlay parts ────────────────────────────────────────────────────────

function ZoneShape({
  z,
  live,
  ring,
  selected,
  onSelect,
  onHover,
}: {
  z: ZoneLayout;
  live?: ZoneLiveState;
  ring: AlarmSeverity | null;
  selected: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null, e?: React.PointerEvent<SVGPathElement>) => void;
}) {
  const s = uiState(live);
  const d = polygonPath(z.points);
  return (
    <g>
      {ring && <path d={d} fill="none" stroke={SEVERITY[ring].color} strokeWidth={5} strokeLinejoin="round" className="map-ring" pointerEvents="none" />}
      <path
        id={`zhit-${z.id}`}
        d={d}
        fill={selected ? 'rgba(255,255,255,0.06)' : 'transparent'}
        stroke={selected ? '#ffffff' : STATE_COLOR[s]}
        strokeWidth={selected ? 2.6 : s === 'idle' ? 1 : 2.2}
        strokeDasharray={s === 'busy' ? '6 4' : undefined}
        strokeLinejoin="round"
        className={`cursor-pointer ${s === 'fault' ? 'map-fault' : s === 'running' ? 'map-glow' : ''}`}
        onClick={() => onSelect(z.id)}
        onPointerMove={(e) => onHover(z.id, e)}
        onPointerLeave={() => onHover(null)}
        role="button"
        aria-label={z.name}
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
    <g fill="none" strokeLinecap="round" strokeLinejoin="round" pointerEvents="none">
      {Object.entries(FARM.network.mainline).map(([name, pts]) => {
        const q = flowByTrunk[name] ?? 0;
        return (
          <g key={name}>
            <path d={polylinePath(pts)} stroke="#0d2a33" strokeWidth={3.6} />
            <path d={polylinePath(pts)} stroke="#2b6577" strokeWidth={2} />
            {q > 0 && (
              <>
                <path d={polylinePath(pts)} stroke={CYAN} strokeOpacity={0.25} strokeWidth={4.5} />
                <path
                  d={polylinePath(pts)}
                  stroke={CYAN}
                  strokeWidth={2}
                  strokeDasharray="5 9"
                  className="map-flow"
                  style={{ animationDuration: `${Math.max(0.5, Math.min(4, 30 / q)) * (TRUNK_LENGTH[name] / 200)}s` }}
                />
              </>
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
            <path d={d} stroke="#2b6577" strokeWidth={1.4} />
            {q > 0.05 && <path d={d} stroke={CYAN} strokeWidth={1.4} strokeDasharray="3 5" className="map-flow" style={{ animationDuration: '0.8s' }} />}
          </g>
        );
      })}
      <path d={polylinePath(FARM.network.refill)} stroke="#2b6577" strokeWidth={1.7} />
      {refill && <path d={polylinePath(FARM.network.refill)} stroke={CYAN} strokeWidth={1.7} strokeDasharray="3 5" className="map-flow" style={{ animationDuration: '1s' }} />}
    </g>
  );
}

const VALVE_COLOR: Record<string, string> = { open: CYAN, opening: '#ffeb3b', closing: '#ffeb3b', fault: '#ff5449' };

function Valves({ valves, alarmed }: { valves: Record<string, ValveLiveState>; alarmed: Set<string> }) {
  return (
    <g pointerEvents="none">
      {ZONES.map((z) => {
        const [x, y] = FARM.network.valves[z.id].valve;
        const v = valves[`valve_${z.id.slice(5)}`];
        const status = v?.status ?? 'closed';
        const open = status === 'open' || status === 'opening';
        const glow = alarmed.has(z.id);
        return (
          <g key={z.id} transform={`translate(${x} ${y})`} className={glow ? 'map-eq-alarm' : undefined}>
            <rect x={-3.4} y={-3.4} width={6.8} height={6.8} rx={1.4} fill="#141414" stroke={glow ? '#ff5449' : '#3b494c'} strokeWidth={0.7} />
            <g className="map-valve" style={{ transform: `rotate(${open ? 90 : 0}deg)` }}>
              <path d="M-2.4,-1.6 L0,0 L-2.4,1.6Z M2.4,-1.6 L0,0 L2.4,1.6Z" fill={VALVE_COLOR[status] ?? '#849396'} />
            </g>
          </g>
        );
      })}
    </g>
  );
}

function Equipment({
  pumps,
  tankPct,
  alarmed,
  t,
}: {
  pumps: Record<string, PumpLiveState>;
  tankPct: number;
  alarmed: Set<string>;
  t: (k: MsgKey) => string;
}) {
  const e = FARM.equipment;
  const rotor = (p: PumpLiveState | undefined, at: Point, r: number) => {
    const color = p?.fault || p?.state === 'failed_start' ? '#ff5449' : p?.state === 'running' ? CYAN : '#849396';
    return (
      <g transform={`translate(${at[0]} ${at[1]})`}>
        <circle r={r + 1.2} fill="#0e0e0e" fillOpacity={0.72} stroke={color} strokeWidth={0.8} />
        <g className={p?.state === 'running' ? 'map-spin' : undefined}>
          {[0, 120, 240].map((a) => (
            <path key={a} d={`M0,0 Q${r * 0.6},${-r * 0.4} ${r},0 Q${r * 0.6},${r * 0.2} 0,0`} fill={color} transform={`rotate(${a})`} />
          ))}
        </g>
      </g>
    );
  };
  const sprite = (key: 'tank' | 'booster' | 'control_room' | 'wellhead', at: Point, label: string, glowKey?: string) => {
    const size = EQUIPMENT_SIZE[key];
    return (
      <g className={glowKey && alarmed.has(glowKey) ? 'map-eq-alarm' : undefined}>
        <circle id={`eq-${key}`} cx={at[0]} cy={at[1]} r={size / 2} fill="transparent" />
        <image href={SPRITES[key]} x={at[0] - size / 2} y={at[1] - size / 2} width={size} height={size} filter="url(#soft-shadow)">
          <title>{label}</title>
        </image>
      </g>
    );
  };
  const tank = e.tank.at;
  const gh = EQUIPMENT_SIZE.tank;
  const gx = tank[0] - gh / 2 - 6;
  const gy = tank[1] - gh / 2;
  const fill = Math.max(0, Math.min(100, tankPct)) / 100;
  const levelColor = tankPct < 10 ? '#ff5449' : tankPct < 25 ? '#ffeb3b' : CYAN;
  return (
    <g pointerEvents="none">
      {sprite('wellhead', e.wellhead.at, t('map.well'), 'wellhead')}
      {sprite('control_room', e.well_room.at, t('map.well'))}
      {sprite('tank', tank, t('map.tank'), 'tank')}
      {sprite('booster', e.booster.at, t('map.booster'), 'booster')}
      {rotor(pumps.pump_booster_01, [e.booster.at[0] + 5, e.booster.at[1] + 3], 2.6)}
      {rotor(pumps.pump_well_01, [e.wellhead.at[0] - 6, e.wellhead.at[1] - 4], 2.2)}
      <g>
        <rect x={gx - 2.2} y={gy} width={4.4} height={gh} rx={1.2} fill="#0e0e0e" stroke="#3b494c" strokeWidth={0.5} />
        <rect x={gx - 1.5} y={gy + gh * (1 - fill)} width={3} height={gh * fill} rx={0.8} fill={levelColor} className="map-tank" />
        <text x={gx} y={gy - 2} textAnchor="middle" fontSize={5} fill={levelColor} direction="ltr" style={{ paintOrder: 'stroke' }} stroke="#000" strokeWidth={1.2}>
          {fmtNum(tankPct)}%
        </text>
      </g>
    </g>
  );
}

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

function mmss(sec: number) {
  const s = Math.max(0, Math.round(sec));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/** Glass name chip + live badge. Counter-scaled so it grows only gently when zooming. */
function Chip({ z, live, alarm, lang }: { z: ZoneLayout; live?: ZoneLiveState; alarm: Alarm | null; lang: 'ar' | 'en' }) {
  const s = uiState(live);
  const [x, y] = z.label;
  const w = z.small ? 60 : 120;
  const h = z.small ? 26 : 46;
  let badge: React.ReactNode;
  if (alarm) {
    badge = (
      <span style={{ color: SEVERITY[alarm.severity].color }}>
        ⚠ <bdi>{alarm.alarm_code}</bdi>
      </span>
    );
  } else if (s === 'running' && live) {
    const left = (live.target_runtime_sec ?? 0) - live.runtime_sec;
    badge = (
      <span style={{ color: CYAN }}>
        ● <bdi>{fmtNum(live.flow_m3h, 1)} m³/h · {mmss(left)}</bdi>
      </span>
    );
  } else if (s === 'busy') {
    badge = <span style={{ color: STATE_COLOR.busy }}>● …</span>;
  } else {
    badge = (
      <span style={{ color: '#bac9cc' }}>
        💧 <bdi>{fmtNum(live?.moisture_pct, 0)}%</bdi>
      </span>
    );
  }
  return (
    <foreignObject x={x - w / 2} y={y - h / 2} width={w} height={h} pointerEvents="none" style={{ overflow: 'visible' }}>
      <div className="map-chip-wrap">
        <div className={`map-chip ${z.small ? 'map-chip-sm' : ''}`} style={{ borderColor: s === 'idle' ? undefined : `${STATE_COLOR[s]}99` }}>
          <div className="map-chip-name">{pickName(lang, z.name, z.nameAr)}</div>
          {!z.small && <div className="map-chip-badge">{badge}</div>}
        </div>
      </div>
    </foreignObject>
  );
}

function Tooltip({ z, live, alarms, lang, t }: { z: ZoneLayout; live?: ZoneLiveState; alarms: Alarm[]; lang: 'ar' | 'en'; t: (k: MsgKey) => string }) {
  const row = (k: MsgKey, v: string) => (
    <div className="flex justify-between gap-4">
      <span className="text-[#849396]">{t(k)}</span>
      <bdi className="font-mono">{v}</bdi>
    </div>
  );
  return (
    <div className="panel p-3 text-xs space-y-1 min-w-48 shadow-2xl">
      <div className="font-bold text-sm mb-1">{pickName(lang, z.name, z.nameAr)}</div>
      {row('zones.state', t(`state.${live?.state ?? 'unknown'}` as MsgKey))}
      {row('zones.moisture', `${fmtNum(live?.moisture_pct, 1)} %`)}
      {row('zones.flow', `${fmtNum(live?.flow_m3h, 2)} m³/h`)}
      {row('zones.pressure', `${fmtNum(live?.pressure_bar, 2)} bar`)}
      {row('zones.source', live?.source_mode ? t(`source.${live.source_mode}` as MsgKey) : '—')}
      {alarms.map((a) => (
        <div key={a.id} className="pt-1" style={{ color: SEVERITY[a.severity].color }}>
          ⚠ <bdi>{a.alarm_code}</bdi> {pickName(lang, a.name, a.name_ar)}
        </div>
      ))}
    </div>
  );
}

// ── map ──────────────────────────────────────────────────────────────────

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
  const reduceMotion = usePrefs((s) => s.reduceMotion);
  const focus = useFarmStore((s) => s.focus);
  const clearFocus = useFarmStore((s) => s.clearFocus);
  const [light, setLight] = useState<Light>('auto');
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState(false);
  const clock = useFarmClock();
  const { night, dusk } = lighting(light, clock.hour);
  const zoomRef = useRef<ReactZoomPanPinchContentRef>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const zoomedRef = useRef(false);

  const zones = useMemo(() => Object.fromEntries((state?.zones ?? []).map((z) => [z.zone_id, z])), [state?.zones]);
  const pumps = useMemo(() => Object.fromEntries((state?.pumps ?? []).map((p) => [p.pump_id, p])), [state?.pumps]);
  const valves = useMemo(() => Object.fromEntries((state?.valves ?? []).map((v) => [v.valve_id, v])), [state?.valves]);
  const alarms = useMemo(() => state?.active_alarms ?? [], [state?.active_alarms]);

  const alarmsByZone = useMemo(() => {
    const m: Record<string, Alarm[]> = {};
    for (const a of alarms) {
      const zid = zoneOfAlarm(a);
      if (zid) (m[zid] ??= []).push(a);
    }
    return m;
  }, [alarms]);
  const alarmedEquipment = useMemo(() => {
    const s = new Set<string>();
    for (const a of alarms) {
      if (!a.condition_active) continue;
      const eq = a.device_id ? EQUIPMENT_FOR_DEVICE[a.device_id] : undefined;
      if (eq) s.add(eq);
      if (a.device_id?.startsWith('valve_')) s.add(`zone_${a.device_id.slice(6)}`);
    }
    return s;
  }, [alarms]);

  const flyTo = (elementId: string) => {
    const el = document.getElementById(elementId);
    if (el && zoomRef.current) zoomRef.current.zoomToElement(el as unknown as HTMLElement, undefined, reduceMotion ? 0 : 700, 'easeOut');
  };

  // fly to a zone when it's selected
  useEffect(() => {
    if (selectedZone) flyTo(`zhit-${selectedZone}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedZone]);

  // fly to the zone / equipment of a new major or critical alarm
  useEffect(() => {
    if (!focus) return;
    const zid = zoneOfAlarm({ zone_id: focus.zoneId, device_id: focus.deviceId });
    const eq = focus.deviceId ? EQUIPMENT_FOR_DEVICE[focus.deviceId] : undefined;
    const target = zid ? `zhit-${zid}` : eq ? `eq-${eq}` : null;
    if (!target) return;
    const timer = setTimeout(() => {
      setFocused(zid ?? null);
      flyTo(target);
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.at]);

  const backToFarm = () => {
    setFocused(null);
    clearFocus();
    zoomRef.current?.resetTransform(reduceMotion ? 0 : 600);
  };

  const dimTarget = focused ?? selectedZone;
  const dimFeature = dimTarget && FARM.features[dimTarget] ? FARM.features[dimTarget].points : null;
  const hoverZone = hover ? ZONES.find((z) => z.id === hover.id) : null;

  const lightModes: { mode: Light; icon: typeof Sun; key: MsgKey }[] = [
    { mode: 'auto', icon: SunMoon, key: 'map.light.auto' },
    { mode: 'day', icon: Sun, key: 'map.light.day' },
    { mode: 'night', icon: Moon, key: 'map.light.night' },
  ];

  return (
    <div ref={rootRef} className="w-full h-full rounded-2xl overflow-hidden relative border border-white/[0.07] bg-[#0b0b0b] shadow-2xl" style={{ containerType: 'size' }}>
      <div className="absolute top-3 start-3 z-20 max-w-[calc(100%-9rem)] flex flex-wrap gap-x-3 gap-y-1 text-[11px] sm:text-xs panel px-2.5 py-1.5 pointer-events-none">
        {(['running', 'busy', 'fault', 'idle'] as UiState[]).map((s) => (
          <span key={s} className="flex items-center gap-1.5" style={{ color: s === 'idle' ? '#bac9cc' : STATE_COLOR[s] }}>
            <span className="w-2.5 h-2.5 rounded-sm border" style={{ borderColor: STATE_COLOR[s], background: s === 'idle' ? 'transparent' : `${STATE_COLOR[s]}33` }} />
            {t(`map.legend.${s}` as MsgKey)}
          </span>
        ))}
      </div>

      <div className="absolute top-3 end-3 z-20 flex gap-1 panel p-1">
        {lightModes.map(({ mode, icon: Icon, key }) => (
          <button
            key={mode}
            onClick={() => setLight(mode)}
            title={t(key)}
            aria-label={t(key)}
            aria-pressed={light === mode}
            className={`p-1.5 rounded-lg ${light === mode ? 'bg-[#00e5ff]/15 text-[#00e5ff]' : 'text-[#849396] hover:text-[#e5e2e1]'}`}
          >
            <Icon size={16} />
          </button>
        ))}
      </div>

      {(focused || selectedZone || zoomed) && (
        <button onClick={backToFarm} className="absolute bottom-3 start-3 z-20 panel flex items-center gap-2 px-3 py-2 text-sm hover:bg-white/10">
          <Undo2 size={16} /> {t('map.back')}
        </button>
      )}

      <TransformWrapper
        ref={zoomRef}
        initialScale={1}
        minScale={0.9}
        maxScale={7}
        centerOnInit
        wheel={{ step: 0.15 }}
        onTransform={(_, s) => {
          boxRef.current?.style.setProperty('--ms', String(s.scale));
          const z = s.scale > 1.08;
          if (z !== zoomedRef.current) {
            zoomedRef.current = z;
            setZoomed(z);
          }
        }}
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="absolute bottom-3 end-3 z-20 flex flex-col gap-2">
              {[
                { f: () => zoomIn(), I: ZoomIn, l: '+' },
                { f: () => zoomOut(), I: ZoomOut, l: '−' },
                { f: () => resetTransform(), I: Maximize, l: 'reset' },
              ].map(({ f, I, l }) => (
                <button key={l} onClick={f} aria-label={l} className="panel p-2 text-[#e5e2e1] hover:bg-white/10">
                  <I size={18} />
                </button>
              ))}
            </div>
            <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full !flex items-center justify-center">
              <div
                ref={boxRef}
                className="relative"
                style={{ width: `min(100cqw, calc(100cqh * ${VW / VH}))`, aspectRatio: `${VW} / ${VH}`, ['--ms' as string]: 1 } as React.CSSProperties}
              >
                <Ground />
                <WetCanvas zones={zones} animate={!reduceMotion} />
                <TreeCanvas zones={zones} month={clock.month} />
                <svg viewBox={`${VX} ${VY} ${VW} ${VH}`} className="absolute inset-0 w-full h-full" role="img" aria-label={t('map.title')}>
                  <OverlayDefs />
                  {ZONES.map((z) => (
                    <ZoneShape
                      key={z.id}
                      z={z}
                      live={zones[z.id]}
                      ring={topSeverity((alarmsByZone[z.id] ?? []).filter((a) => a.condition_active))}
                      selected={selectedZone === z.id}
                      onSelect={onZoneSelect}
                      onHover={(id, e) => {
                        const r = rootRef.current?.getBoundingClientRect();
                        if (!id || !e || !r) return setHover(null);
                        setHover({ id, x: e.clientX - r.left, y: e.clientY - r.top });
                      }}
                    />
                  ))}
                  <Pipes zones={zones} pumps={pumps} />
                  <Valves valves={valves} alarmed={alarmedEquipment} />
                  <Equipment pumps={pumps} tankPct={state?.tank_level_pct ?? 0} alarmed={alarmedEquipment} t={t} />
                  {!reduceMotion && <FarmLife alarms={alarms} />}
                  {dimFeature && (
                    <path
                      d={`M${VX},${VY}H${VW}V${VH}H${VX}Z ${polygonPath(dimFeature)}`}
                      fillRule="evenodd"
                      fill="#000"
                      opacity={0.45}
                      pointerEvents="none"
                      className="map-dim"
                    />
                  )}
                  {dusk > 0 && <rect x={VX} y={VY} width={VW} height={VH} fill="#ff8a3d" opacity={dusk * 0.18} style={{ mixBlendMode: 'soft-light' }} pointerEvents="none" />}
                  {night > 0 && <rect x={VX} y={VY} width={VW} height={VH} fill="#0a1430" opacity={night * 0.6} style={{ mixBlendMode: 'multiply' }} pointerEvents="none" />}
                  <Lamps night={night} />
                  {ZONES.map((z) => (
                    <Chip key={z.id} z={z} live={zones[z.id]} alarm={(alarmsByZone[z.id] ?? []).find((a) => a.condition_active) ?? null} lang={lang} />
                  ))}
                </svg>
              </div>
            </TransformComponent>
          </>
        )}
      </TransformWrapper>

      {hover && hoverZone && (
        <div className="absolute z-30 pointer-events-none" style={{ left: hover.x + 14, top: hover.y + 14 }}>
          <Tooltip z={hoverZone} live={zones[hoverZone.id]} alarms={alarmsByZone[hoverZone.id] ?? []} lang={lang} t={t} />
        </div>
      )}
    </div>
  );
}
