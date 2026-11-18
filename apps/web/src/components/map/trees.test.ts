import { describe, expect, it } from 'vitest';
import { FARM } from '@algaroshy/map-model';
import { ZONES } from './farmLayout';
import { FRUIT_SEASON, placeTrees, pointInPolygon, spriteFor } from './trees';

describe('tree placement', () => {
  it('places a realistic number of trees inside each field', () => {
    let total = 0;
    for (const z of ZONES) {
      const trees = placeTrees(z);
      total += trees.length;
      expect(trees.length, z.id).toBeGreaterThan(z.small ? 3 : 40);
      for (const t of trees) expect(pointInPolygon([t.x, t.y], z.points), z.id).toBe(true);
    }
    // 11.9 ha at 4-7 m spacing → a few thousand trees, not tens of thousands
    expect(total).toBeGreaterThan(1500);
    expect(total).toBeLessThan(8000);
  });

  it('density matches the crop: olives sparser than pomegranates', () => {
    const area = (id: string) => FARM.features[id].legend_m2;
    const per = (id: string) => placeTrees(ZONES.find((z) => z.id === id)!).length / area(id);
    expect(per('zone_zaytoun')).toBeLessThan(per('zone_rumman_6'));
  });

  it('is deterministic (every viewer sees the same orchard)', () => {
    const z = ZONES[0];
    expect(placeTrees(z)).toEqual(placeTrees(z));
  });

  it('mixed block interleaves peach, apricot and plum', () => {
    const species = new Set(placeTrees(ZONES.find((z) => z.id === 'zone_fruit_mix')!).map((t) => t.species));
    expect(species).toEqual(new Set(['peach', 'apricot', 'plum']));
  });

  it('shows fruit only in season', () => {
    expect(FRUIT_SEASON.pomegranate).toContain(11);
    expect(spriteFor('pomegranate', 11)).toContain('fruit');
    expect(spriteFor('pomegranate', 3)).toContain('green');
    expect(spriteFor('apricot', 11)).toContain('stonefruit_green');
  });
});
