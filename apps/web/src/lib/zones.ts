/**
 * Live zone catalog (Milestone G3). The database is the single source of zone names, crops
 * and settings; the owner edits them in Settings → Zones & equipment. Components read
 * `ZONE_BY_ID` (kept up to date in place) or `zoneList()`; the built-in seeds are only the
 * starting point until the API answers.
 */
import { useEffect } from 'react';
import { create } from 'zustand';
import { ZONE_SEEDS, type Zone } from '@algaroshy/contracts';
import { usePoll } from './poll';

export const ZONES_PATH = '/api/v1/zones';

export const ZONE_BY_ID: Record<string, Zone> = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, { ...z }]));

/** Bumped whenever the catalog changes, so subscribers re-render. */
export const useZoneCatalog = create<{ version: number }>(() => ({ version: 0 }));

export function applyZones(list: Partial<Zone>[]): void {
  for (const z of list) {
    if (!z.id) continue;
    ZONE_BY_ID[z.id] = { ...(ZONE_BY_ID[z.id] ?? {}), ...z, name_ar: z.name_ar ?? z.name ?? '' } as Zone;
  }
  useZoneCatalog.setState((s) => ({ version: s.version + 1 }));
}

export function zoneList({ enabledOnly = false } = {}): Zone[] {
  return Object.values(ZONE_BY_ID)
    .filter((z) => !enabledOnly || z.enabled !== false)
    .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99) || a.id.localeCompare(b.id));
}

/** Mount once (layout): keeps the catalog synced with the API; returns a render version. */
export function useZoneCatalogSync(): number {
  const data = usePoll<Zone[]>(ZONES_PATH, 60_000);
  useEffect(() => {
    if (Array.isArray(data)) applyZones(data);
  }, [data]);
  return useZoneCatalog((s) => s.version);
}
