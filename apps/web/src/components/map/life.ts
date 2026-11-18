/**
 * Walkable network for farm life (worker, tractor): dirt tracks + mainline
 * corridors as a graph, with shortest-path routing (Dijkstra) and a helper to
 * follow a polyline at constant speed.
 */
import { FARM, type Point } from '@algaroshy/map-model';

type Graph = { nodes: Point[]; edges: Map<number, { to: number; w: number }[]> };

const MERGE = 6; // map units: endpoints closer than this are the same junction

function build(): Graph {
  const nodes: Point[] = [];
  const edges = new Map<number, { to: number; w: number }[]>();
  const nodeFor = (p: Point) => {
    const i = nodes.findIndex((n) => Math.hypot(n[0] - p[0], n[1] - p[1]) < MERGE);
    if (i >= 0) return i;
    nodes.push(p);
    return nodes.length - 1;
  };
  const link = (a: number, b: number) => {
    if (a === b) return;
    const w = Math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1]);
    (edges.get(a) ?? edges.set(a, []).get(a)!).push({ to: b, w });
    (edges.get(b) ?? edges.set(b, []).get(b)!).push({ to: a, w });
  };
  const lines: Point[][] = [...FARM.tracks, ...Object.values(FARM.network.mainline), FARM.network.refill];
  for (const line of lines) {
    for (let i = 1; i < line.length; i++) link(nodeFor(line[i - 1]), nodeFor(line[i]));
  }
  return { nodes, edges };
}

export const WALK = build();

function nearestNode(p: Point): number {
  let best = 0;
  let bd = Infinity;
  WALK.nodes.forEach((n, i) => {
    const d = Math.hypot(n[0] - p[0], n[1] - p[1]);
    if (d < bd) {
      bd = d;
      best = i;
    }
  });
  return best;
}

/** Shortest walkable route from `from` to `to` (both arbitrary points). */
export function route(from: Point, to: Point): Point[] {
  const s = nearestNode(from);
  const t = nearestNode(to);
  const dist = new Map<number, number>([[s, 0]]);
  const prev = new Map<number, number>();
  const open = new Set<number>([s]);
  while (open.size) {
    let u = -1;
    let ud = Infinity;
    for (const n of open) {
      const d = dist.get(n) ?? Infinity;
      if (d < ud) {
        ud = d;
        u = n;
      }
    }
    open.delete(u);
    if (u === t) break;
    for (const { to: v, w } of WALK.edges.get(u) ?? []) {
      const nd = ud + w;
      if (nd < (dist.get(v) ?? Infinity)) {
        dist.set(v, nd);
        prev.set(v, u);
        open.add(v);
      }
    }
  }
  const path: Point[] = [];
  for (let n: number | undefined = t; n !== undefined; n = prev.get(n)) path.unshift(WALK.nodes[n]);
  if (path[0] !== WALK.nodes[s]) return [from, to]; // disconnected: walk straight
  return [from, ...path, to];
}

export function pathLength(path: Point[]): number {
  let l = 0;
  for (let i = 1; i < path.length; i++) l += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
  return l;
}

/** Position + heading (deg) at distance `d` along `path`. */
export function along(path: Point[], d: number): { p: Point; heading: number } {
  let rest = Math.max(0, d);
  for (let i = 1; i < path.length; i++) {
    const [ax, ay] = path[i - 1];
    const [bx, by] = path[i];
    const seg = Math.hypot(bx - ax, by - ay);
    if (rest <= seg || i === path.length - 1) {
      const f = seg ? Math.min(1, rest / seg) : 0;
      return { p: [ax + (bx - ax) * f, ay + (by - ay) * f], heading: (Math.atan2(by - ay, bx - ax) * 180) / Math.PI };
    }
    rest -= seg;
  }
  return { p: path[path.length - 1], heading: 0 };
}
