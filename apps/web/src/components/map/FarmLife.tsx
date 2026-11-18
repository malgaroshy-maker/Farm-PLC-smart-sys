/**
 * Life on the farm (SVG overlay, driven by requestAnimationFrame — no React
 * re-render per frame):
 *  - tractor: works back and forth along a field-edge track
 *  - worker: idles near the control room; walks to the valve of a zone with an
 *            active zone/valve alarm and stays until it's acked/cleared
 *  - birds:  a small flock crosses the farm every 25–50 s, wings flapping
 * Hidden entirely when reduce-motion is on.
 */
import { useEffect, useRef } from 'react';
import type { Alarm } from '@algaroshy/contracts';
import { FARM, type Point } from '@algaroshy/map-model';
import { along, pathLength, route } from './life';

const [, , VW, VH] = FARM.viewBox;
const WORKER_SPEED = 2.7; // map units / s ≈ 1.4 m/s walking
const TRACTOR_SPEED = 3.5;
const HOME: Point = [FARM.equipment.well_room.at[0] + 9, FARM.equipment.well_room.at[1] + 7];

function setT(el: SVGGElement | null, p: Point, heading: number, scale = 1) {
  el?.setAttribute('transform', `translate(${p[0].toFixed(2)} ${p[1].toFixed(2)}) rotate(${heading.toFixed(1)}) scale(${scale})`);
}

/** The zone whose alarm the worker should attend (first open, unacked zone/valve alarm). */
function targetZone(alarms: Alarm[]): string | null {
  const a = alarms.find((x) => x.zone_id && x.status === 'active_unacked');
  return a?.zone_id ?? null;
}

export default function FarmLife({ alarms }: { alarms: Alarm[] }) {
  const tractor = useRef<SVGGElement>(null);
  const worker = useRef<SVGGElement>(null);
  const birds = useRef<SVGGElement>(null);
  const target = targetZone(alarms);
  const targetRef = useRef<string | null>(target);
  useEffect(() => {
    targetRef.current = target;
  }, [target]);

  useEffect(() => {
    let raf = 0;
    let prev = performance.now();

    // tractor: longest track, ping-pong
    const track = [...FARM.tracks].sort((a, b) => pathLength(b) - pathLength(a))[0];
    const trackLen = pathLength(track);
    let tractorD = 0;
    let tractorDir = 1;
    let tractorPause = 0;

    // worker state machine
    let wPos: Point = HOME;
    let wPath: Point[] | null = null;
    let wD = 0;
    let wGoal: string | null = null;
    let wHeading = 0;
    let idleT = 0;

    // birds
    let flock: { from: Point; to: Point; t: number; dur: number } | null = null;
    let nextFlock = performance.now() + 6000;

    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - prev) / 1000);
      prev = now;

      // ── tractor
      if (tractorPause > 0) tractorPause -= dt;
      else {
        tractorD += tractorDir * TRACTOR_SPEED * dt;
        if (tractorD >= trackLen || tractorD <= 0) {
          tractorD = Math.max(0, Math.min(trackLen, tractorD));
          tractorDir *= -1;
          tractorPause = 4;
        }
      }
      const tp = along(track, tractorD);
      setT(tractor.current, tp.p, tp.heading + (tractorDir < 0 ? 180 : 0));

      // ── worker
      const goalZone = targetRef.current;
      if (goalZone !== wGoal) {
        wGoal = goalZone;
        const dest = goalZone ? FARM.network.valves[goalZone]?.valve ?? HOME : HOME;
        wPath = route(wPos, dest);
        wD = 0;
      }
      if (wPath) {
        wD += WORKER_SPEED * dt;
        const w = along(wPath, wD);
        wPos = w.p;
        wHeading = w.heading;
        if (wD >= pathLength(wPath)) wPath = null; // arrived
        setT(worker.current, wPos, wHeading, 1 + 0.04 * Math.sin(now / 140)); // walking bob
      } else {
        // idle: small fidget (inspecting the valve / waiting at the control room)
        idleT += dt;
        setT(worker.current, [wPos[0] + Math.sin(idleT * 0.7) * 0.8, wPos[1] + Math.cos(idleT * 0.5) * 0.6], wHeading + Math.sin(idleT * 0.4) * 25);
      }

      // ── birds
      if (!flock && now > nextFlock) {
        const y0 = VH * (0.15 + Math.random() * 0.7);
        const ltr = Math.random() < 0.5;
        flock = { from: [ltr ? -40 : VW + 40, y0], to: [ltr ? VW + 40 : -40, y0 + (Math.random() - 0.5) * VH * 0.5], t: 0, dur: 14 + Math.random() * 6 };
      }
      if (flock) {
        flock.t += dt;
        const f = flock.t / flock.dur;
        const x = flock.from[0] + (flock.to[0] - flock.from[0]) * f;
        const y = flock.from[1] + (flock.to[1] - flock.from[1]) * f;
        const heading = (Math.atan2(flock.to[1] - flock.from[1], flock.to[0] - flock.from[0]) * 180) / Math.PI;
        birds.current?.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${heading.toFixed(1)})`);
        birds.current?.querySelectorAll<SVGGElement>('[data-wing]').forEach((b, i) => {
          b.setAttribute('transform', `scale(1 ${(0.55 + 0.45 * Math.abs(Math.sin(now / 110 + i))).toFixed(2)})`);
        });
        if (f >= 1) {
          flock = null;
          nextFlock = now + 25000 + Math.random() * 25000;
          birds.current?.setAttribute('transform', 'translate(-999 -999)');
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <g pointerEvents="none">
      <g ref={tractor}>
        <ellipse cx={1.5} cy={1.5} rx={7} ry={2.4} fill="#000" opacity={0.25} />
        <image href="/map/spr_tractor.webp" x={-9} y={-3.4} width={18} height={6.8} />
      </g>
      <g ref={worker}>
        <ellipse cx={0.8} cy={0.8} rx={1.8} ry={1.6} fill="#000" opacity={0.3} />
        <image href="/map/spr_worker.webp" x={-2.2} y={-2.4} width={4.4} height={4.8} />
      </g>
      <g ref={birds} transform="translate(-999 -999)">
        {[
          [0, 0],
          [-9, 6],
          [-7, -7],
        ].map(([dx, dy], i) => (
          <g key={i} transform={`translate(${dx} ${dy})`}>
            {/* shadow far below the bird */}
            <ellipse cx={14} cy={18} rx={2.6} ry={1.2} fill="#000" opacity={0.18} />
            <g data-wing="">
              <image href="/map/spr_bird.webp" x={-3} y={-4.3} width={6} height={8.6} />
            </g>
          </g>
        ))}
      </g>
    </g>
  );
}
