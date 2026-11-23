import { describe, expect, it } from 'vitest';
import { FARM, ZONE_IDS, areaM2, polygonCentroid } from './index';

// Owner-approved satellite trace (2026-11-23). Areas are measured on the satellite;
// the sketch legend is a cross-check: every zone is within -8 %..+16 % of it.
const SATELLITE_M2: Record<string, number> = {
  zone_zaytoun: 21090,
  zone_rumman_6: 7791,
  zone_rumman_5: 6616,
  zone_rumman_ummahat: 1614,
  zone_enab: 734,
  zone_zaytoun_2: 1737,
  zone_fruit_mix: 10871,
  zone_rumman_jadeed: 10760,
  zone_rumman_3: 5230,
  zone_rumman_4: 7891,
  zone_rumman_2: 7730,
  zone_rumman_1: 5595,
};

describe('farm geometry', () => {
  it('has all 12 zones plus boundary, tank and well', () => {
    expect(ZONE_IDS).toHaveLength(12);
    for (const k of ['boundary', 'tank', 'well']) expect(FARM.features[k]).toBeDefined();
  });

  it('zone areas match the satellite trace (drawn polygons are inset by half a track)', () => {
    for (const id of ZONE_IDS) {
      expect(FARM.features[id].area_m2, id).toBe(SATELLITE_M2[id]);
      // the drawn polygon stops at the track edge: 75-95 % of the area to the track centre
      const ratio = areaM2(id) / SATELLITE_M2[id];
      expect(ratio, id).toBeGreaterThan(0.5);
      expect(ratio, id).toBeLessThan(0.97);
    }
  });

  it('satellite areas stay within 20 % of the sketch legend', () => {
    for (const id of ZONE_IDS) {
      const ratio = SATELLITE_M2[id] / FARM.features[id].legend_m2;
      expect(ratio, id).toBeGreaterThan(0.8);
      expect(ratio, id).toBeLessThan(1.2);
    }
  });

  it('is true scale: ~0.5 m per unit', () => {
    expect(Math.sqrt(FARM.m2_per_unit2)).toBeCloseTo(0.5035, 3);
  });

  it('every zone has a valve inside the viewBox, and a measured row direction', () => {
    const [, , w, h] = FARM.viewBox;
    for (const id of ZONE_IDS) {
      expect(FARM.network.valves[id], id).toBeDefined();
      expect(FARM.features[id].row_angle_deg, id).toBeTypeOf('number');
      const [cx, cy] = polygonCentroid(FARM.features[id].points);
      expect(cx).toBeGreaterThan(0);
      expect(cx).toBeLessThan(w);
      expect(cy).toBeGreaterThan(0);
      expect(cy).toBeLessThan(h);
    }
  });

  it('the rest house is inside the farm boundary', () => {
    const [hx, hy] = polygonCentroid(FARM.buildings.resthouse.points);
    const b = FARM.features.boundary.points;
    let inside = false;
    for (let i = 0, j = b.length - 1; i < b.length; j = i++) {
      const [xi, yi] = b[i];
      const [xj, yj] = b[j];
      if (yi > hy !== yj > hy && hx < ((xj - xi) * (hy - yi)) / (yj - yi) + xi) inside = !inside;
    }
    expect(inside).toBe(true);
  });

  it('has the owner-confirmed buildings and surroundings', () => {
    expect(Object.keys(FARM.buildings).sort()).toEqual(['barn', 'brooder', 'control', 'resthouse', 'rooms', 'tank']);
    expect(FARM.buildings.control.kind).toBe('control_room');
    expect(FARM.buildings.tank.kind).toBe('tank');
    expect(FARM.buildings.resthouse.name_ar).toBe('استراحة المزرعة');
    expect(FARM.surroundings.wadi.points.length).toBeGreaterThan(3);
    expect(FARM.network.guessed).toBe(true);
  });
});
