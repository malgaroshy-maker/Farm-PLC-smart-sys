import { describe, expect, it } from 'vitest';
import { TRUNK_PARENT, ZONES } from './farmLayout';

describe('map layout', () => {
  it('maps each zone to a crop texture, a name and a feeding trunk', () => {
    expect(ZONES).toHaveLength(12);
    for (const z of ZONES) {
      expect(z.name, z.id).not.toBe(z.id);
      expect(z.nameAr, z.id).toMatch(/[؀-ۿ]/);
      expect(Object.keys(TRUNK_PARENT)).toContain(z.trunk);
    }
    const crop = Object.fromEntries(ZONES.map((z) => [z.id, z.crop]));
    expect(crop.zone_rumman_1).toBe('pomegranate');
    expect(crop.zone_zaytoun).toBe('olive');
    expect(crop.zone_enab).toBe('grape');
    expect(crop.zone_fruit_mix).toBe('mixed');
  });

  it('the east branch hangs off the south-east trunk; trunks from the tank have no parent', () => {
    expect(TRUNK_PARENT.branch_e).toBe('trunk_se');
    expect(TRUNK_PARENT.trunk_se).toBeUndefined();
    expect(TRUNK_PARENT.trunk_ne).toBeUndefined();
  });

  it('labels the fruit block with plum (عوينة), not guava', () => {
    const fruit = ZONES.find((z) => z.id === 'zone_fruit_mix')!;
    expect(fruit.nameAr).toContain('عوينة');
    expect(fruit.name).toContain('Plum');
  });
});
