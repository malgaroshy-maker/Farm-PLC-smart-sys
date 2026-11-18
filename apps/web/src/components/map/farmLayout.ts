/**
 * Static, derived map data: per-zone crop texture + row direction, label anchors,
 * which mainline trunk feeds which zone, equipment footprints. Computed once.
 */
import { FARM, ZONE_IDS, polygonCentroid, polylineLength, type Point } from '@algaroshy/map-model';
import { ZONE_SEEDS } from '@algaroshy/contracts';

export type Crop = 'pomegranate' | 'olive' | 'grape' | 'mixed';

/** Tile size in map units (1 unit ≈ 0.51 m) so trees appear at real spacing. */
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
  wellhead: '/map/spr_wellhead.webp',
};

function cropFor(zoneId: string): Crop {
  if (zoneId.startsWith('zone_rumman')) return 'pomegranate';
  if (zoneId.startsWith('zone_zaytoun')) return 'olive';
  if (zoneId === 'zone_enab') return 'grape';
  return 'mixed';
}

/** Angle (deg) of the polygon's longest edge — tree rows run along it. */
function rowAngle(points: Point[]): number {
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
  points: Point[];
  label: Point;
  small: boolean;
  trunk: string;
}

const seedById = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));

export const ZONES: ZoneLayout[] = ZONE_IDS.map((id) => {
  const f = FARM.features[id];
  const seed = seedById[id];
  return {
    id,
    name: seed?.name ?? id,
    nameAr: seed?.name_ar ?? id,
    crop: cropFor(id),
    angle: rowAngle(f.points),
    points: f.points,
    label: polygonCentroid(f.points),
    small: f.legend_m2 < 2000,
    trunk: nearestTrunk(FARM.network.valves[id].tap),
  };
});

export const TRUNK_LENGTH: Record<string, number> = Object.fromEntries(
  trunkNames.map((n) => [n, polylineLength(trunks[n])]),
);

/** Sprite footprints in map units (real size × 1.4 so they read at farm zoom). */
export const EQUIPMENT_SIZE = { tank: 26, booster: 15, control_room: 20, wellhead: 10 };
