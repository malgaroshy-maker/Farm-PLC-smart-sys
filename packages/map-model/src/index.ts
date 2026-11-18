/**
 * Farm map geometry — traced from the owner's sketch, areas verified against its legend.
 * Regenerate with tools/map-geometry/ (see README there). Coordinates are map units
 * in `viewBox`; `m2_per_unit2` converts polygon area to square metres.
 */
import raw from './farm-geometry.json';

export type Point = [number, number];

export interface FarmFeature {
  points: Point[];
  legend_m2: number;
}

export interface FarmGeometry {
  viewBox: [number, number, number, number];
  m2_per_unit2: number;
  features: Record<string, FarmFeature>;
  network: {
    mainline: Record<string, Point[]>;
    refill: Point[];
    valves: Record<string, { tap: Point; valve: Point }>;
  };
  tracks: Point[][];
  equipment: Record<string, { at: Point; kind: 'tank_building' | 'booster_pad' | 'control_room' | 'wellhead' }>;
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
