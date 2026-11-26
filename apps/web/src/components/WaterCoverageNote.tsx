import type { WaterCoverage } from '@algaroshy/contracts';
import { useT } from '../lib/i18n';

export default function WaterCoverageNote({ coverage, unavailable = false }: {
  coverage?: WaterCoverage;
  unavailable?: boolean;
}) {
  const { t, isRtl } = useT();
  const notes = [];
  if (unavailable) notes.push(t('water.unavailable'));
  else {
    if (coverage?.water_is_estimate) notes.push(t('water.includesEstimates'));
    if (coverage?.water_has_gaps) notes.push(t('water.hasGaps'));
  }
  return notes.length ? (
    <div className="mt-1 text-xs text-[#849396]">{notes.join(isRtl ? '، ' : ' · ')}</div>
  ) : null;
}
