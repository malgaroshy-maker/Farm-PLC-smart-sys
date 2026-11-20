import { useT } from '../../lib/i18n';

export interface ModelBadgeProps {
  modelUsed?: string | null;
  provider?: string | null;
  className?: string;
}

export default function ModelBadge({ modelUsed, provider, className = '' }: ModelBadgeProps) {
  const { t } = useT();

  const isRuleBased =
    !modelUsed ||
    provider === 'rule_based' ||
    modelUsed === 'rule_based' ||
    modelUsed === 'rule-based-fallback' ||
    modelUsed === 'cancelled';

  if (isRuleBased) {
    return (
      <span
        data-testid="model-badge-fallback"
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border bg-amber-500/10 text-amber-300 border-amber-500/30 ${className}`}
      >
        <span>{t('ai.ruleBased')}</span>
      </span>
    );
  }

  // Strip 'free/' prefix from model name
  const cleanModel = modelUsed.replace(/^free\//, '');
  const displayText = provider && provider !== 'system' && provider !== 'APInex'
    ? `${cleanModel} • ${provider}`
    : provider === 'APInex'
    ? `${cleanModel} • APInex`
    : cleanModel;

  return (
    <span
      data-testid="model-badge"
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono border bg-white/5 text-[#849396] border-white/10 ${className}`}
    >
      <span className="text-[#00e5ff]/70 font-sans text-[9px] font-bold">{t('ai.modelBadge')}:</span>
      <span>{displayText}</span>
    </span>
  );
}
