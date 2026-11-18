import { describe, expect, it } from 'vitest';
import { FARM, ZONE_IDS, areaM2, polygonCentroid } from './index';

describe('farm geometry', () => {
  it('has all 12 zones plus boundary, tank and well', () => {
    expect(ZONE_IDS).toHaveLength(12);
    for (const k of ['boundary', 'tank', 'well']) expect(FARM.features[k]).toBeDefined();
  });

  it('traced areas match the sketch legend within ±12%', () => {
    for (const [id, f] of Object.entries(FARM.features)) {
      const ratio = areaM2(id) / f.legend_m2;
      expect(ratio, id).toBeGreaterThan(0.88);
      expect(ratio, id).toBeLessThan(1.12);
    }
  });

  it('every zone has a valve and lies inside the viewBox', () => {
    const [, , w, h] = FARM.viewBox;
    for (const id of ZONE_IDS) {
      expect(FARM.network.valves[id], id).toBeDefined();
      const [cx, cy] = polygonCentroid(FARM.features[id].points);
      expect(cx).toBeGreaterThan(0);
      expect(cx).toBeLessThan(w);
      expect(cy).toBeGreaterThan(0);
      expect(cy).toBeLessThan(h);
    }
  });
});
