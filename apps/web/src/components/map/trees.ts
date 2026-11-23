/**
 * Individual tree placement: rows along each field's row direction at real
 * agronomic spacing, kept inside the polygon, with seeded jitter so every
 * render (and every viewer) sees the same orchard.
 *
 * Map units: 1 unit ≈ 0.5 m (sqrt of FARM.m2_per_unit2). Row direction and row spacing
 * come from the satellite where measured (farmLayout); the rest uses crop defaults.
 */
import { FARM, type Point } from '@algaroshy/map-model';
import type { Crop, ZoneLayout } from './farmLayout';

const M = 1 / Math.sqrt(FARM.m2_per_unit2); // map units per metre

/** row spacing, in-row spacing, canopy diameter (metres) */
const SPACING: Record<Crop, { row: number; tree: number; canopy: number; elongated?: boolean }> = {
  pomegranate: { row: 5, tree: 4, canopy: 3.6 },
  olive: { row: 7, tree: 7, canopy: 5.6 },
  grape: { row: 3, tree: 3, canopy: 3.1, elongated: true }, // trellis segments end-to-end
  mixed: { row: 5.5, tree: 5, canopy: 4.2 },
};

export type Species = 'pomegranate' | 'olive' | 'grape' | 'peach' | 'apricot' | 'plum' | 'almond' | 'lemon' | 'orange';

export interface Tree {
  x: number;
  y: number;
  /** canopy diameter in map units */
  size: number;
  /** degrees */
  rotation: number;
  species: Species;
}

/** Harvest months (1-12) per species — fruit sprites shown only in season. */
export const FRUIT_SEASON: Record<Species, number[]> = {
  pomegranate: [9, 10, 11],
  olive: [10, 11, 12],
  grape: [7, 8, 9],
  apricot: [5, 6],
  peach: [6, 7, 8],
  plum: [6, 7, 8],
  almond: [8, 9],
  lemon: [11, 12, 1, 2, 3],
  orange: [12, 1, 2, 3],
};

export function spriteFor(species: Species, month: number): string {
  const fruit = FRUIT_SEASON[species].includes(month);
  switch (species) {
    case 'pomegranate':
      return fruit ? '/map/tree_pomegranate_fruit.webp' : '/map/tree_pomegranate_green.webp';
    case 'olive':
      return fruit ? '/map/tree_olive_fruit.webp' : '/map/tree_olive_green.webp';
    case 'grape':
      return fruit ? '/map/tree_grape_fruit.webp' : '/map/tree_grape_green.webp';
    case 'peach':
      return fruit ? '/map/tree_peach_fruit.webp' : '/map/tree_stonefruit_green.webp';
    case 'apricot':
      return fruit ? '/map/tree_apricot_fruit.webp' : '/map/tree_stonefruit_green.webp';
    case 'plum':
      return fruit ? '/map/tree_plum_fruit.webp' : '/map/tree_stonefruit_green.webp';
    case 'almond':
      return fruit ? '/map/tree_almond_fruit.webp' : '/map/tree_almond_green.webp';
    case 'lemon':
      return fruit ? '/map/tree_lemon_fruit.webp' : '/map/tree_citrus_green.webp';
    case 'orange':
      return fruit ? '/map/tree_orange_fruit.webp' : '/map/tree_citrus_green.webp';
  }
}

export function pointInPolygon([x, y]: Point, poly: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function distToEdge([x, y]: Point, poly: Point[]): number {
  let best = Infinity;
  for (let i = 0; i < poly.length; i++) {
    const [ax, ay] = poly[i];
    const [bx, by] = poly[(i + 1) % poly.length];
    const dx = bx - ax;
    const dy = by - ay;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1)));
    best = Math.min(best, Math.hypot(x - (ax + t * dx), y - (ay + t * dy)));
  }
  return best;
}

/** mulberry32 — tiny deterministic PRNG */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

const MIXED: Species[] = ['peach', 'apricot', 'plum'];

export function placeTrees(zone: ZoneLayout): Tree[] {
  const sp = SPACING[zone.crop];
  const rowStep = (zone.rowSpacing ?? sp.row) * M;
  const treeStep = (zone.treeSpacing ?? sp.tree) * M;
  const canopy = (zone.canopy ?? sp.canopy) * M;
  const fitted = zone.rowCount != null || zone.small;
  // fitted strips keep their outer rows: only a small edge margin
  const margin = canopy * (fitted ? 0.2 : 0.55);
  const rand = rng(hash(zone.id));

  // rotate the polygon into row-aligned space (rows parallel to the x' axis)
  const a = (-zone.angle * Math.PI) / 180;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  const toLocal = ([x, y]: Point): Point => [x * cos - y * sin, x * sin + y * cos];
  const toWorld = ([x, y]: Point): Point => [x * cos + y * sin, -x * sin + y * cos];
  const local = zone.points.map(toLocal);
  const xs = local.map((p) => p[0]);
  const ys = local.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];

  // rows run parallel to the field and are centred across it, so they line up with the edges
  const width = maxY - minY;
  const nRows = zone.rowCount ?? Math.max(1, Math.floor(width / rowStep));
  const y0 = minY + (width - (nRows - 1) * rowStep) / 2;

  const trees: Tree[] = [];
  for (let row = 0; row < nRows; row++) {
    const y = y0 + row * rowStep;
    const offset = zone.crop === 'olive' && row % 2 ? treeStep / 2 : 0; // staggered olive grid
    for (let x = minX + treeStep / 2 + offset; x < maxX; x += treeStep) {
      const jitter = sp.elongated ? 0 : treeStep * 0.08;
      const p = toWorld([x + (rand() - 0.5) * jitter, y + (rand() - 0.5) * jitter]);
      if (!pointInPolygon(p, zone.points) || distToEdge(p, zone.points) < margin) continue;
      const species: Species =
        zone.crop === 'pomegranate'
          ? 'pomegranate'
          : zone.crop === 'olive'
            ? 'olive'
            : zone.crop === 'grape'
              ? 'grape'
              : zone.species?.length
                ? zone.species[Math.floor(rand() * zone.species.length)]
                : MIXED[row % 3];
      trees.push({
        x: p[0],
        y: p[1],
        size: canopy * (sp.elongated ? 1 : 0.88 + rand() * 0.24),
        rotation: sp.elongated ? zone.angle : rand() * 360,
        species,
      });
    }
  }
  return trees;
}

export const TREES: Record<string, Tree[]> = {};
export function treesFor(zone: ZoneLayout): Tree[] {
  return (TREES[zone.id] ??= placeTrees(zone));
}
