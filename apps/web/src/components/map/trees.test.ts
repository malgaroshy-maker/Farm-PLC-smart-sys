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

describe('trees outside zones', () => {
  it('the mixed-fruit strip grows almond, lemon, orange, apricot and plum', async () => {
    const { OTHER_TREES } = await import('./farmLayout');
    const strip = OTHER_TREES.find((z) => z.id === 'other_mixed_fruit_strip')!;
    const species = new Set(placeTrees(strip).map((t) => t.species));
    for (const s of ['almond', 'lemon', 'orange']) expect(species, s).toContain(s);
    expect(spriteFor('lemon', 1)).toContain('lemon_fruit');
    expect(spriteFor('orange', 7)).toContain('citrus_green');
  });
});

describe('block 8 rows (owner 2026-11-23)', () => {
  it('zaytoun_2 has exactly three rows of big olives', () => {
    const z = ZONES.find((x) => x.id === 'zone_zaytoun_2')!;
    const trees = placeTrees(z);
    const a = (z.angle * Math.PI) / 180;
    const across = new Set(trees.map((t) => Math.round(-t.x * Math.sin(a) + t.y * Math.cos(a))));
    // three row lines (allowing 1 unit of rounding / jitter either side)
    const rows = [...across].sort((p, q) => p - q).reduce<number[]>((acc, v) => (acc.length && v - acc[acc.length - 1] < 4 ? acc : [...acc, v]), []);
    expect(rows).toHaveLength(3);
    expect(trees.every((t) => t.species === 'olive')).toBe(true);
  });

  it('ummahat mother trees are bigger than the other pomegranates; enab is trellis rows', () => {
    const size = (id: string) => {
      const t = placeTrees(ZONES.find((x) => x.id === id)!);
      return t.reduce((s, x) => s + x.size, 0) / t.length;
    };
    const mothers = placeTrees(ZONES.find((x) => x.id === 'zone_rumman_ummahat')!);
    expect(mothers.every((t) => t.species === 'pomegranate')).toBe(true);
    expect(mothers.length).toBeGreaterThan(10);
    expect(size('zone_rumman_ummahat')).toBeGreaterThan(size('zone_rumman_4') * 1.3);
    const grapes = placeTrees(ZONES.find((x) => x.id === 'zone_enab')!);
    expect(grapes.every((t) => t.species === 'grape')).toBe(true);
  });
});
