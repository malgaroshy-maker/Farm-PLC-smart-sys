/**
 * Static, derived map data: per-zone crop texture + row direction, label anchors,
 * which mainline trunk feeds which zone, equipment footprints. Computed once.
 */
import { FARM, ZONE_IDS, polygonCentroid, polylineLength, type Point } from '@algaroshy/map-model';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import type { Species } from './trees';

export type Crop = 'pomegranate' | 'olive' | 'grape' | 'mixed';

/** Tile size in map units (1 unit ≈ 0.5 m) so trees appear at real spacing. */
export const TEXTURES: Record<Crop | 'sand' | 'track', { href: string; w: number; h: number }> = {
  pomegranate: { href: '/map/tex_pomegranate.webp', w: 34, h: 34 },
  olive: { href: '/map/tex_olive.webp', w: 46, h: 46 },
  grape: { href: '/map/tex_grape.webp', w: 26, h: 26 },
  mixed: { href: '/map/tex_mixed_fruit.webp', w: 46, h: 46 },
  sand: { href: '/map/tex_sand.webp', w: 150, h: 100 },
  track: { href: '/map/tex_track.webp', w: 60, h: 30 },
};

export const SPRITES = {
  tank: '/map/spr_tank.webp',
  booster: '/map/spr_booster.webp',
  control_room: '/map/spr_control_room.webp',
  wellhead: '/map/spr_well_cap.webp', // the well is underground: a flush cap
};

function cropFor(zoneId: string): Crop {
  if (zoneId.startsWith('zone_rumman')) return 'pomegranate';
  if (zoneId.startsWith('zone_zaytoun')) return 'olive';
  if (zoneId === 'zone_enab') return 'grape';
  return 'mixed';
}

/**
 * SVG angle (deg, from +x, y down) of the tree rows. Uses the row bearing measured on
 * the satellite (clockwise from north) when there is one, else the longest edge.
 */
export function rowAngle(points: Point[], bearingDeg?: number | null): number {
  if (bearingDeg != null) return bearingDeg - 90;
  let best = 0;
  let angle = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    const len = Math.hypot(x2 - x1, y2 - y1);
    if (len > best) {
      best = len;
      angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
    }
  }
  return angle;
}

function distToPolyline(p: Point, line: Point[]): number {
  let best = Infinity;
  for (let i = 1; i < line.length; i++) {
    const [ax, ay] = line[i - 1];
    const [bx, by] = line[i];
    const dx = bx - ax;
    const dy = by - ay;
    const t = Math.max(0, Math.min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy || 1)));
    best = Math.min(best, Math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)));
  }
  return best;
}

const trunks = FARM.network.mainline;
const trunkNames = Object.keys(trunks);

function nearestTrunk(p: Point, exclude?: string): string {
  return trunkNames
    .filter((n) => n !== exclude)
    .reduce((a, b) => (distToPolyline(p, trunks[a]) <= distToPolyline(p, trunks[b]) ? a : b));
}

const tankAt = FARM.equipment.tank.at;

/** Branches that don't start at the tank hang off another trunk. */
export const TRUNK_PARENT: Record<string, string | undefined> = Object.fromEntries(
  trunkNames.map((n) => {
    const [sx, sy] = trunks[n][0];
    const fromTank = Math.hypot(sx - tankAt[0], sy - tankAt[1]) < 3;
    return [n, fromTank ? undefined : nearestTrunk(trunks[n][0], n)];
  }),
);

export interface ZoneLayout {
  id: string;
  name: string;
  nameAr: string;
  crop: Crop;
  angle: number;
  /** measured metres between rows / trees; undefined → crop default */
  rowSpacing?: number;
  treeSpacing?: number;
  /** trees outside a zone: species mix to draw */
  species?: Species[];
  /** exact number of rows (owner), centred across the field */
  rowCount?: number;
  /** canopy diameter override in metres (e.g. big old olives) */
  canopy?: number;
  points: Point[];
  label: Point;
  small: boolean;
  trunk: string;
}

/** Trees that belong to no zone (e.g. the mixed-fruit strip): drawn, not clickable. */
export const OTHER_TREES: ZoneLayout[] = Object.entries(FARM.other_trees ?? {}).map(([id, o]) => ({
  id: `other_${id}`,
  name: id,
  nameAr: id,
  crop: 'mixed',
  species: o.species as Species[],
  angle: rowAngle(o.points),
  points: o.points,
  label: polygonCentroid(o.points),
  small: true,
  trunk: '',
}));

/** Zone-specific canopy diameter / in-row spacing (metres), from the owner. */
const CANOPY_M: Record<string, number> = { zone_zaytoun_2: 6.8, zone_rumman_ummahat: 5.4 };
const TREE_SPACING_M: Record<string, number> = { zone_rumman_ummahat: 4.6 };

const seedById = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));

export const ZONES: ZoneLayout[] = ZONE_IDS.map((id) => {
  const f = FARM.features[id];
  const seed = seedById[id];
  return {
    id,
    name: seed?.name ?? id,
    nameAr: seed?.name_ar ?? id,
    crop: cropFor(id),
    angle: rowAngle(f.points, f.row_angle_deg),
    rowSpacing: f.row_spacing_m ?? undefined,
    rowCount: f.row_count,
    // owner: big old olives in zaytoun_2; the mother pomegranates (ummahat) are bigger than the other pomegranates
    canopy: CANOPY_M[id],
    treeSpacing: f.tree_spacing_m ?? TREE_SPACING_M[id],
    points: f.points,
    label: polygonCentroid(f.points),
    small: f.legend_m2 < 2000,
    trunk: nearestTrunk(FARM.network.valves[id].tap),
  };
});

/**
 * Small zones (block 8 strips) get their name written inside the strip, along it,
 * instead of a chip (owner 2026-11-23). The angle keeps the text readable (never upside down).
 */
export const STRIP_LABEL_H = 9;
export const STRIP_LABELS: Record<string, { at: Point; angle: number; length: number }> = Object.fromEntries(
  ZONES.filter((z) => z.small).map((z) => {
    let a = ((z.angle % 180) + 180) % 180; // 0..180
    if (a > 90) a -= 180; // -90..90: never upside down
    const rad = (a * Math.PI) / 180;
    const proj = z.points.map(([x, y]) => x * Math.cos(rad) + y * Math.sin(rad));
    return [z.id, { at: z.label, angle: a, length: Math.max(...proj) - Math.min(...proj) }];
  }),
);

export const TRUNK_LENGTH: Record<string, number> =Object.fromEntries(
  trunkNames.map((n) => [n, polylineLength(trunks[n])]),
);

/** Sprite footprints in map units (real size × 1.4 so they read at farm zoom). */
export const EQUIPMENT_SIZE = { tank: 26, booster: 15, control_room: 20, wellhead: 8 };
