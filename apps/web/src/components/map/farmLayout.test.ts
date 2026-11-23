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
    // tank → trunk_se (south along the main track) and trunk_w (west); the rest branch off trunk_se
    expect(TRUNK_PARENT.trunk_se).toBeUndefined();
    expect(TRUNK_PARENT.trunk_w).toBeUndefined();
    expect(TRUNK_PARENT.trunk_n).toBe('trunk_se');
    expect(TRUNK_PARENT.branch_x1).toBe('trunk_se');
    expect(TRUNK_PARENT.branch_x2).toBe('trunk_se');
  });

  it('uses the satellite row direction: pomegranate rows run NNW-SSE, olive rows NE-SW', () => {
    const angle = (id: string) => ((ZONES.find((z) => z.id === id)!.angle % 180) + 180) % 180;
    expect(angle('zone_rumman_4')).toBeGreaterThan(55); // bearing ~158° → svg ~68°
    expect(angle('zone_rumman_4')).toBeLessThan(75);
    expect(angle('zone_zaytoun')).toBeGreaterThan(140); // bearing ~56° → svg ~-34° ≡ 146°
    expect(angle('zone_zaytoun')).toBeLessThan(155);
  });

  it('labels the fruit block with plum (عوينة), not guava', () => {
    const fruit = ZONES.find((z) => z.id === 'zone_fruit_mix')!;
    expect(fruit.nameAr).toContain('عوينة');
    expect(fruit.name).toContain('Plum');
  });
});

describe('block 8 strips', () => {
  it('label each strip inside it, along the rows', async () => {
    const { STRIP_LABELS, ZONES } = await import('./farmLayout');
    expect(Object.keys(STRIP_LABELS).sort()).toEqual(['zone_enab', 'zone_rumman_ummahat', 'zone_zaytoun_2']);
    for (const [id, l] of Object.entries(STRIP_LABELS)) {
      const z = ZONES.find((x) => x.id === id)!;
      const diff = (((l.angle - z.angle) % 180) + 180) % 180;
      expect(Math.min(diff, 180 - diff), id).toBeLessThan(0.01); // parallel to the rows
      expect(Math.abs(l.angle), id).toBeLessThanOrEqual(90); // never upside down
    }
  });

  it('all three strips share one row direction, parallel to the strip edges', async () => {
    const { ZONES } = await import('./farmLayout');
    const a = ['zone_rumman_ummahat', 'zone_enab', 'zone_zaytoun_2'].map((id) => ZONES.find((z) => z.id === id)!.angle);
    expect(new Set(a).size).toBe(1);
  });
});
