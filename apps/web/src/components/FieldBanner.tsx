/**
 * G7 field banner (owner's choice): shown under the top bar while something at the farm is not in
 * its normal automatic state: switches on the panel not on Auto, mains power off, or the PLC
 * running its own copy of today's program because it can't reach the app.
 */
import { Hand, PlugZap, ServerOff } from 'lucide-react';
import { useFarmStore } from '../store/farm';
import { useT } from '../lib/i18n';

export default function FieldBanner() {
  const { t } = useT();
  const state = useFarmStore((s) => s.state);
  if (!state) return null;
  const manual =
    state.zones.filter((z) => z.panel_mode && z.panel_mode !== 'auto').length +
    state.pumps.filter((p) => p.panel_mode && p.panel_mode !== 'auto').length;
  const rows: { key: string; icon: typeof Hand; text: string; color: string }[] = [];
  if (state.power_ok === false) rows.push({ key: 'power', icon: PlugZap, text: t('banner.power'), color: '#ff5449' });
  if (state.fallback_active) rows.push({ key: 'fallback', icon: ServerOff, text: t('banner.fallback'), color: '#ff9f43' });
  if (manual > 0) rows.push({ key: 'manual', icon: Hand, text: t('banner.manual').replace('{n}', String(manual)), color: '#ff9f43' });
  if (!rows.length) return null;
  return (
    <div role="status" aria-live="polite" className="shrink-0 border-b border-white/10 bg-[#141416]">
      {rows.map(({ key, icon: Icon, text, color }) => (
        <div key={key} className="flex items-center gap-2 px-3 lg:px-6 py-2 text-sm" style={{ color }}>
          <Icon size={16} aria-hidden="true" className="shrink-0" />
          <span>{text}</span>
        </div>
      ))}
    </div>
  );
}
