/**
 * Feature switches (Milestone G3). The owner turns features on/off on the Settings page;
 * the UI hides what is switched off. While loading, everything counts as on, so nothing
 * flickers away on start-up.
 */
import { useEffect } from 'react';
import { refreshPoll, usePoll } from './poll';

export const FEATURES_PATH = '/api/v1/system/features';

export interface FeaturesResponse {
  features: Record<string, boolean>;
  groups: Record<string, string>;
  defaults: Record<string, boolean>;
}

export function useFeaturesData(): FeaturesResponse | null {
  return usePoll<FeaturesResponse>(FEATURES_PATH, 60_000);
}

export function useFeature(key: string): boolean {
  return useFeaturesData()?.features[key] ?? true;
}

/** Re-read the switches now (after a change here or a `features.updated` event). */
export function refreshFeatures(): void {
  refreshPoll(FEATURES_PATH);
}

/**
 * Mirrors switched-off features onto <html data-feature-off="…"> so plain CSS can hide
 * scattered buttons (e.g. every "Explain with AI" button) without threading props.
 */
export function useFeatureAttributes(): void {
  const data = useFeaturesData();
  useEffect(() => {
    if (!data) return;
    const off = Object.entries(data.features)
      .filter(([, on]) => !on)
      .map(([k]) => k)
      .join(' ');
    document.documentElement.dataset.featureOff = off;
  }, [data]);
}
