/**
 * Farm map geometry — traced on satellite imagery (Esri World Imagery z17), north-up and
 * true scale, owner-approved 2026-11-23. Regenerate with tools/map-geometry/satellite_retrace.py
 * (see README there). Coordinates are map units in `viewBox` (1 unit ≈ 0.5 m);
 * `m2_per_unit2` converts polygon area to square metres.
 */
import raw from './farm-geometry.json';

export type Point = [number, number];

export interface FarmFeature {
  points: Point[];
  /** area from the owner's sketch legend */
  legend_m2: number;
  /** area measured on the satellite (to the track centre line) */
  area_m2?: number;
  /** tree-row bearing, degrees clockwise from north (0–180), measured on the satellite */
  row_angle_deg?: number | null;
  /** metres between tree rows, measured; null → crop default */
  row_spacing_m?: number | null;
  /** metres between trees in a row; null → crop default (not resolvable at ~1 m/px) */
  tree_spacing_m?: number | null;
  /** exact number of tree rows when the owner gave it (rows are centred across the field) */
  row_count?: number;
}

export type BuildingKind = 'chicken_house' | 'workers' | 'control_room' | 'tank' | 'house';

export interface FarmGeometry {
  attribution?: string;
  viewBox: [number, number, number, number];
  m2_per_unit2: number;
  features: Record<string, FarmFeature>;
  network: {
    /** pipes are not visible from the satellite: routes follow the tracks and are guessed */
    guessed?: boolean;
    mainline: Record<string, Point[]>;
    refill: Point[];
    valves: Record<string, { tap: Point; valve: Point; trunk?: string }>;
  };
  tracks: Point[][];
  /** narrow footpaths (between the block 8 strips) */
  paths?: Point[][];
  equipment: Record<string, { at: Point; kind: 'tank_building' | 'booster_pad' | 'control_room' | 'wellhead' }>;
  /** non-irrigation buildings: labelled, not interactive */
  buildings: Record<string, { points: Point[]; kind: BuildingKind; sprite?: string | null; name: string; name_ar: string }>;
  /** trees that belong to no zone (drawn, not clickable) */
  other_trees: Record<string, { points: Point[]; species: string[] }>;
  /** not ours: faded, not clickable, no labels */
  surroundings: { orchards: Point[][]; wadi: { width: number; points: Point[] } };
}

export const FARM: FarmGeometry = raw as unknown as FarmGeometry;

export const ZONE_IDS = Object.keys(FARM.features).filter((k) => k.startsWith('zone_'));

/** SVG path data for a closed polygon. */
export function polygonPath(points: Point[]): string {
  return `M${points.map(([x, y]) => `${x},${y}`).join('L')}Z`;
}

/** SVG path data for an open polyline. */
export function polylinePath(points: Point[]): string {
  return `M${points.map(([x, y]) => `${x},${y}`).join('L')}`;
}

/** Shoelace area in map units². */
export function polygonArea(points: Point[]): number {
  let a = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

/** Area-weighted centroid — a good label anchor for convex-ish fields. */
export function polygonCentroid(points: Point[]): Point {
  let cx = 0;
  let cy = 0;
  let a = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    const f = x1 * y2 - x2 * y1;
    a += f;
    cx += (x1 + x2) * f;
    cy += (y1 + y2) * f;
  }
  a /= 2;
  return [cx / (6 * a), cy / (6 * a)];
}

export function areaM2(featureId: string): number {
  return polygonArea(FARM.features[featureId].points) * FARM.m2_per_unit2;
}

/** Polyline length in map units (for flow-animation dash timing). */
export function polylineLength(points: Point[]): number {
  let len = 0;
  for (let i = 1; i < points.length; i++) {
    len += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
  }
  return len;
}
