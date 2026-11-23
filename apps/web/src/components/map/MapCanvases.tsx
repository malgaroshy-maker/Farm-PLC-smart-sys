/**
 * Canvas layers under the interactive SVG overlay:
 *  - WetCanvas:  damp soil spreading under each tree + cyan wet rings + drip
 *                sparkles, animated only while a zone irrigates.
 *  - TreeCanvas: ~3,000 individual tree sprites with shadows; redrawn only
 *                when the season or a zone's dryness bucket changes.
 * Both render at a fixed high resolution so zooming stays sharp.
 */
import { memo, useEffect, useMemo, useRef } from 'react';
import type { ZoneLiveState } from '@algaroshy/contracts';
import { FARM } from '@algaroshy/map-model';
import { OTHER_TREES, ZONES } from './farmLayout';
import { spriteFor, treesFor, type Tree } from './trees';

const [, , VW, VH] = FARM.viewBox;
// sharper on large screens; phones keep a smaller canvas to save memory
const CANVAS_W = typeof window !== "undefined" && window.innerWidth >= 1200 ? 3600 : 2400;
const S = CANVAS_W / VW;
const CANVAS_H = Math.round(VH * S);

const imageCache = new Map<string, Promise<HTMLImageElement>>();
function loadImage(src: string): Promise<HTMLImageElement> {
  if (!imageCache.has(src)) {
    imageCache.set(
      src,
      new Promise((resolve, reject) => {
        const img = new Image();
        img.decoding = 'async';
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
      }),
    );
  }
  return imageCache.get(src)!;
}

/** 0 (fine) … 1 (very dry), quantised so small moisture wiggles don't redraw. */
function dryness(moisture: number | null | undefined): number {
  if (moisture == null) return 0;
  return Math.round(Math.max(0, Math.min(1, (28 - moisture) / 18)) * 4) / 4;
}

function drawTree(ctx: CanvasRenderingContext2D, t: Tree, img: HTMLImageElement) {
  const w = t.size * S;
  const h = (w * img.height) / img.width;
  const elongated = img.width > img.height * 2;
  // soft contact shadow, sun from the upper left
  ctx.save();
  ctx.translate(t.x * S + w * 0.12, t.y * S + w * 0.1);
  ctx.rotate(elongated ? (t.rotation * Math.PI) / 180 : 0);
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, w * 0.55);
  g.addColorStop(0, 'rgba(20,14,6,0.42)');
  g.addColorStop(1, 'rgba(20,14,6,0)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.ellipse(0, 0, w * 0.55, (elongated ? h * 0.9 : w * 0.5), 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.translate(t.x * S, t.y * S);
  ctx.rotate((t.rotation * Math.PI) / 180);
  ctx.drawImage(img, -w / 2, -h / 2, w, h);
  ctx.restore();
}

export const TreeCanvas = memo(function TreeCanvas({
  zones,
  month,
}: {
  zones: Record<string, ZoneLiveState>;
  month: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  // redraw key: season + per-zone dryness bucket
  const key = useMemo(
    () => `${month}|${ZONES.map((z) => dryness(zones[z.id]?.moisture_pct)).join(',')}`,
    [zones, month],
  );

  useEffect(() => {
    let cancelled = false;
    const ctx = ref.current?.getContext('2d');
    if (!ctx) return;
    const srcs = new Set<string>();
    for (const z of [...ZONES, ...OTHER_TREES]) for (const t of treesFor(z)) srcs.add(spriteFor(t.species, month));
    Promise.all([...srcs].map(loadImage)).then(() => {
      if (cancelled) return;
      ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
      // trees outside any zone (not irrigated by this system): no dryness tint
      for (const z of OTHER_TREES) {
        for (const t of treesFor(z)) {
          const img = imageCache.get(spriteFor(t.species, month));
          img?.then((im) => !cancelled && drawTree(ctx, t, im));
        }
      }
      for (const z of ZONES) {
        const d = dryness(zones[z.id]?.moisture_pct);
        // drought stress: canopy loses saturation and shifts toward yellow
        ctx.filter = d > 0 ? `sepia(${0.55 * d}) saturate(${1 - 0.35 * d}) hue-rotate(-${12 * d}deg) brightness(${1 + 0.1 * d})` : 'none';
        for (const t of treesFor(z)) {
          const img = imageCache.get(spriteFor(t.species, month));
          img?.then((im) => !cancelled && drawTree(ctx, t, im));
        }
      }
      ctx.filter = 'none';
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return <canvas ref={ref} width={CANVAS_W} height={CANVAS_H} className="absolute inset-0 w-full h-full pointer-events-none" />;
});

function phase(t: Tree): number {
  return ((t.x * 12.9898 + t.y * 78.233) % 1 + 1) % 1;
}

export const WetCanvas = memo(function WetCanvas({
  zones,
  animate,
}: {
  zones: Record<string, ZoneLiveState>;
  animate: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zonesRef = useRef(zones);
  useEffect(() => {
    zonesRef.current = zones;
  }, [zones]);
  const staticZones = animate ? null : zones;

  useEffect(() => {
    const ctx = ref.current?.getContext('2d');
    if (!ctx) return;
    let raf = 0;
    let last = 0;

    const draw = (now: number) => {
      const live = zonesRef.current;
      ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
      for (const z of ZONES) {
        const zl = live[z.id];
        const flowing = (zl?.flow_m3h ?? 0) > 0.05;
        if (!flowing) continue;
        // wet area grows over the first ~10 minutes of a cycle
        const wet = Math.min(1, 0.35 + (zl?.runtime_sec ?? 0) / 600);
        for (const t of treesFor(z)) {
          const x = t.x * S;
          const y = t.y * S;
          const r = t.size * S * (0.45 + 0.35 * wet);
          const g = ctx.createRadialGradient(x, y, 0, x, y, r);
          g.addColorStop(0, 'rgba(38,24,10,0.62)');
          g.addColorStop(0.7, 'rgba(48,30,12,0.32)');
          g.addColorStop(1, 'rgba(48,30,12,0)');
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
          if (!animate) continue;
          // spreading wet ring
          const p = ((now / 2600 + phase(t)) % 1 + 1) % 1;
          ctx.strokeStyle = `rgba(0,229,255,${0.38 * (1 - p)})`;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.arc(x, y, r * (0.55 + 0.6 * p), 0, Math.PI * 2);
          ctx.stroke();
          // drip sparkle at the emitter on the drip line (east side of the trunk)
          const blink = Math.max(0, Math.sin((now / 380 + phase(t) * 6.28) * 1.0));
          if (blink > 0.85) {
            ctx.fillStyle = `rgba(190,250,255,${(blink - 0.85) * 6})`;
            ctx.beginPath();
            ctx.arc(x + r * 0.35, y, 1.6, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    };

    const loop = (now: number) => {
      if (now - last > 33) {
        last = now;
        draw(now);
      }
      raf = requestAnimationFrame(loop);
    };
    if (animate) raf = requestAnimationFrame(loop);
    else draw(0);
    return () => cancelAnimationFrame(raf);
    // the animated loop reads zonesRef; only the static drawing needs a redraw per update
  }, [animate, staticZones]);

  return <canvas ref={ref} width={CANVAS_W} height={CANVAS_H} className="absolute inset-0 w-full h-full pointer-events-none" />;
});
