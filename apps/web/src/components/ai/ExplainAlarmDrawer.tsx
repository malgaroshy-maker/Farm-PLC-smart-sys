import { useEffect, useState, useRef } from 'react';
import { X, AlertTriangle, ShieldAlert, Sparkles, Send, Wrench, XCircle, Copy, Check } from 'lucide-react';
import type { Alarm } from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import { explainAlarm, type AlarmExplanation, type ChatMessage, sendAiChat } from '../../lib/api';
import { SEVERITY } from '../../lib/alarms';
import { pickName, useT } from '../../lib/i18n';
import { AiSparklesIcon } from '../icons/FarmIcons';
import ModelBadge from './ModelBadge';
import { useElapsedSeconds } from '../../hooks/useElapsedSeconds';

interface ExplainAlarmDrawerProps {
  alarm: Alarm | null;
  onClose: () => void;
}

const ZONE_MAP = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));

export default function ExplainAlarmDrawer({ alarm, onClose }: ExplainAlarmDrawerProps) {
  if (!alarm) return null;
  return <ExplainAlarmDrawerContent key={alarm.id} alarm={alarm} onClose={onClose} />;
}

function ExplainAlarmDrawerContent({ alarm, onClose }: { alarm: Alarm; onClose: () => void }) {
  const { t, lang, isRtl } = useT();
  const [loading, setLoading] = useState(true);
  const [explanation, setExplanation] = useState<AlarmExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const chatAbortControllerRef = useRef<AbortController | null>(null);

  // Follow-up chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Timers & Copy states
  const elapsedSec = useElapsedSeconds(loading);
  const chatElapsedSec = useElapsedSeconds(chatLoading);
  const [copiedSummary, setCopiedSummary] = useState(false);
  const [copiedChatIdx, setCopiedChatIdx] = useState<number | null>(null);

  const handleCopyText = async (text: string, isSummary = true, idx?: number) => {
    try {
      await navigator.clipboard.writeText(text);
      if (isSummary) {
        setCopiedSummary(true);
        setTimeout(() => setCopiedSummary(false), 2000);
      } else if (idx !== undefined) {
        setCopiedChatIdx(idx);
        setTimeout(() => setCopiedChatIdx(null), 2000);
      }
    } catch {
      /* clipboard write failed */
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    explainAlarm(alarm.id, undefined, lang, controller.signal)
      .then((res) => {
        if (!active) return;
        setExplanation(res);
      })
      .catch((err: unknown) => {
        if (!active || controller.signal.aborted) return;
        // Fallback rule-based explanation derived directly from alarm metadata
        const fallback: AlarmExplanation = {
          alarm_id: alarm.id,
          summary:
            (lang === 'ar'
              ? alarm.message_ar || alarm.message_en
              : alarm.message_en || alarm.message_ar) || '',
          likely_causes:
            lang === 'ar'
              ? [
                  `انحراف القيمة الحالية (${alarm.current_value ?? '--'}) عن الحد المقبول (${alarm.threshold_value ?? '--'})`,
                  'احتمال وجود عطل ميكانيكي أو انسداد أو تسريب في المسار المحدد',
                  'استجابة بطيئة في فتح/إغلاق الصمامات أو إشارة الحساس',
                ]
              : [
                  `Current telemetry value (${alarm.current_value ?? '--'}) crossed threshold (${alarm.threshold_value ?? '--'})`,
                  'Possible mechanical restriction, valve delay, or pipe leakage in monitored segment',
                  'Transient pressure surge or sensor wiring anomaly',
                ],
          steps:
            lang === 'ar'
              ? [
                  alarm.guidance_ar || alarm.guidance_en || 'تحقق من خط الري والصمامات ميدانياً',
                  'افحص مقياس الضغط ومؤشر التدفق على لوحة الأجهزة',
                  'تأكد من عدم وجود تسريب ظاهر أو انسداد في فلاتر الخط',
                  alarm.requires_manual_reset
                    ? 'بعد المعالجة الميدانية، قم بإعادة تعيين الإنذار يدوياً من مركز الإنذارات'
                    : 'سيزول الإنذار تلقائياً بمجرد عودة القراءات للنطاق الطبيعي',
                ]
              : [
                  alarm.guidance_en || alarm.guidance_ar || 'Inspect irrigation line and valves on site',
                  'Check physical pressure gauge and flow meter readout',
                  'Confirm no visible pipe rupture, filter clogging, or dry run condition',
                  alarm.requires_manual_reset
                    ? 'Perform manual reset in Alarm Center once field check is verified'
                    : 'Alarm clears automatically when telemetry returns to normal range',
                ],
          safety_note:
            lang === 'ar'
              ? 'تنبيه سلامة: لا تقم بتجاوز حمايات PLC أو تشغيل المضخة قسرياً عند هبوط الضغط الحاد.'
              : 'Safety note: Never bypass PLC interlocks or force pump start during abnormal pressure drops.',
          provider: 'rule_based',
          model: 'rule-based-fallback',
          is_fallback: true,
          fallback_reason: 'rule_based_fallback',
        };
        setExplanation(fallback);
        if (err instanceof Error && !err.message.includes('404')) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [alarm, lang]);

  const handleCancelExplain = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setLoading(false);
    const fallback: AlarmExplanation = {
      alarm_id: alarm.id,
      summary:
        (lang === 'ar'
          ? alarm.message_ar || alarm.message_en
          : alarm.message_en || alarm.message_ar) || '',
      likely_causes:
        lang === 'ar'
          ? [
              `انحراف القيمة الحالية (${alarm.current_value ?? '--'}) عن الحد المقبول (${alarm.threshold_value ?? '--'})`,
              'تم إلغاء الطلب بواسطة المشغّل وتم تطبيق التشخيص الميداني المباشر',
            ]
          : [
              `Current telemetry value (${alarm.current_value ?? '--'}) crossed threshold (${alarm.threshold_value ?? '--'})`,
              'Request cancelled by operator — direct field diagnosis loaded',
            ],
      steps:
        lang === 'ar'
          ? [
              alarm.guidance_ar || alarm.guidance_en || 'تحقق من خط الري والصمامات ميدانياً',
              'افحص مقياس الضغط ومؤشر التدفق على لوحة الأجهزة',
            ]
          : [
              alarm.guidance_en || alarm.guidance_ar || 'Inspect irrigation line and valves on site',
              'Check physical pressure gauge and flow meter readout',
            ],
      safety_note:
        lang === 'ar'
          ? 'تنبيه سلامة: لا تقم بتجاوز حمايات PLC أو تشغيل المضخة قسرياً عند هبوط الضغط الحاد.'
          : 'Safety note: Never bypass PLC interlocks or force pump start during abnormal pressure drops.',
      provider: 'rule_based',
      model: 'rule-based-fallback',
      is_fallback: true,
      fallback_reason: 'cancelled_by_operator',
    };
    setExplanation(fallback);
  };

  const handleCancelChat = () => {
    if (chatAbortControllerRef.current) {
      chatAbortControllerRef.current.abort();
    }
    setChatLoading(false);
  };

  const handleSendFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = inputQuestion.trim();
    if (!q || chatLoading || !alarm) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: q,
      created_at: new Date().toISOString(),
    };

    const nextMessages = [...chatMessages, userMsg];
    setChatMessages(nextMessages);
    setInputQuestion('');
    setChatLoading(true);

    const controller = new AbortController();
    chatAbortControllerRef.current = controller;

    try {
      const response = await explainAlarm(alarm.id, q, lang, controller.signal);
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: response.summary,
        provider: response.provider,
        model: response.model,
        is_fallback: response.is_fallback,
        latency_ms: response.latency_ms,
        fallback_reason: response.fallback_reason,
        created_at: new Date().toISOString(),
      };
      setChatMessages([...nextMessages, assistantMsg]);
    } catch {
      if (controller.signal.aborted) {
        setChatMessages([
          ...nextMessages,
          {
            role: 'assistant',
            content: t('ai.cancelled'),
            provider: 'rule_based',
            model: 'cancelled',
            is_fallback: true,
            created_at: new Date().toISOString(),
          },
        ]);
        return;
      }

      // Try general AI chat endpoint as secondary fallback
      try {
        const promptContext = `Context: Alarm ${alarm.alarm_code} (${alarm.name} / ${alarm.name_ar}), Zone ${alarm.zone_id ?? 'System'}. Question: ${q}`;
        const chatRes = await sendAiChat([{ role: 'user', content: promptContext }], lang, controller.signal);
        setChatMessages([
          ...nextMessages,
          {
            role: 'assistant',
            content: chatRes.message,
            provider: chatRes.provider,
            model: chatRes.model,
            is_fallback: chatRes.is_fallback,
            latency_ms: chatRes.latency_ms,
            fallback_reason: chatRes.fallback_reason,
            created_at: new Date().toISOString(),
          },
        ]);
      } catch {
        if (controller.signal.aborted) return;
        setChatMessages([
          ...nextMessages,
          {
            role: 'assistant',
            content:
              lang === 'ar'
                ? `بناءً على الكتالوج للإنذار ${alarm.alarm_code}: ${alarm.guidance_ar || alarm.guidance_en}. يرجى فحص الموقع والتأكد من سلامة الحساسات والأنابيب.`
                : `Based on guidance for ${alarm.alarm_code}: ${alarm.guidance_en || alarm.guidance_ar}. Please inspect field hardware and verify sensor readings.`,
            provider: 'rule_based',
            model: 'rule-based-fallback',
            is_fallback: true,
            fallback_reason: 'connection_fallback',
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } finally {
      setChatLoading(false);
      setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  };

  if (!alarm) return null;

  const sev = alarm.severity;
  const sevColor = SEVERITY[sev].color;
  const zone = alarm.zone_id ? ZONE_MAP[alarm.zone_id] : null;
  const zoneDisplayName = zone ? pickName(lang, zone.name, zone.name_ar) : alarm.zone_id || alarm.device_id || t('al.system');

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-50 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${t('ai.explain')} ${alarm.alarm_code}`}
        className="fixed top-0 end-0 h-full w-[480px] max-w-full z-50 flex flex-col text-[#e5e2e1] bg-[#121214]/95 backdrop-blur-xl border-s border-white/10 shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="p-4 sm:p-5 flex items-start gap-3 border-b border-white/10 bg-white/5">
          <span
            className="p-2.5 rounded-xl border flex items-center justify-center shrink-0"
            style={{
              borderColor: `${sevColor}55`,
              backgroundColor: `${sevColor}15`,
              color: sevColor,
            }}
          >
            <AlertTriangle size={22} />
          </span>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold px-1.5 py-0.5 rounded bg-black/40 border border-white/10 text-[#00e5ff]" dir="ltr">
                {alarm.alarm_code}
              </span>
              <span
                className="text-[11px] font-bold px-1.5 py-0.5 rounded"
                style={{ backgroundColor: `${sevColor}22`, color: sevColor }}
              >
                {lang === 'ar' ? SEVERITY[sev].labelAr : SEVERITY[sev].label}
              </span>
            </div>
            <h2 className="text-base font-bold text-[#e5e2e1] mt-1 truncate">
              {pickName(lang, alarm.name, alarm.name_ar)}
            </h2>
            <div className="text-xs text-[#849396] truncate">
              {zoneDisplayName}
            </div>
          </div>

          <button
            onClick={onClose}
            aria-label={t('drawer.close')}
            className="p-2 rounded-lg text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1] transition-colors"
          >
            <X size={19} />
          </button>
        </div>

        {/* Provider Banner */}
        <div className="px-4 py-2 border-b border-white/5 bg-black/40 flex items-center justify-between text-xs flex-wrap gap-2">
          <div className="flex items-center gap-1.5 text-[#00e5ff] flex-wrap">
            <AiSparklesIcon size={15} />
            <span className="font-medium">
              {explanation?.is_fallback || explanation?.provider === 'rule_based'
                ? t('ai.ruleBasedLabel')
                : (explanation?.provider || 'APInex')}
            </span>
            {!explanation?.is_fallback && (explanation?.model_used || explanation?.model) && (
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-[#00e5ff] border border-white/10">
                {explanation?.model_used || explanation?.model}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {explanation?.latency_ms !== undefined && explanation.latency_ms > 0 && (
              <span className="text-[11px] text-[#00e5ff] font-mono">
                {explanation.latency_ms >= 1000
                  ? `${(explanation.latency_ms / 1000).toFixed(1)} s`
                  : `${explanation.latency_ms} ms`}
              </span>
            )}
            {explanation?.fallback_reason && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ff9f43]/15 text-[#ff9f43] border border-[#ff9f43]/30">
                {explanation.fallback_reason}
              </span>
            )}
            {explanation?.confidence !== undefined && (
              <span className="text-[11px] text-[#849396] font-mono">
                {Math.round(explanation.confidence * 100)}%
              </span>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {loading ? (
            <div className="py-12 px-4 flex flex-col items-center justify-center text-center space-y-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-4 border-[#00e5ff]/20 border-t-[#00e5ff] animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Sparkles size={18} className="text-[#00e5ff] animate-pulse" />
                </div>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[#e5e2e1]">
                  {lang === 'ar' ? `جاري التفكير... (${elapsedSec} ث)` : `Thinking... (${elapsedSec}s)`}
                </h3>
                <p className="text-xs text-[#849396]">{alarm.alarm_code} · {pickName(lang, alarm.name, alarm.name_ar)}</p>
              </div>
              <button
                type="button"
                onClick={handleCancelExplain}
                className="px-4 py-1.5 rounded-xl border border-white/20 hover:border-[#ff5449] hover:bg-[#ff5449]/10 text-xs text-[#bac9cc] hover:text-[#ffb4ab] transition-colors"
              >
                {t('ai.cancel')}
              </button>
            </div>
          ) : (
            <>
              {error && (
                <div className="text-xs text-[#ffeb3b] bg-[#ffeb3b]/10 border border-[#ffeb3b]/20 p-2.5 rounded-lg">
                  {error}
                </div>
              )}

              {/* Diagnosis Summary Card */}
              <section className="panel p-4 space-y-3 border-[#00e5ff]/20">
                <div className="flex items-center justify-between text-xs font-bold text-[#00e5ff]">
                  <span className="flex items-center gap-2">
                    <Sparkles size={15} />
                    <span>{t('ai.diagnosis')}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopyText(explanation ? pickName(lang, explanation.summary, explanation.summary_ar) : '')}
                    className="flex items-center gap-1 text-[11px] text-[#849396] hover:text-[#e5e2e1] px-2 py-1 rounded-lg hover:bg-white/10 transition-colors"
                    title={t('ai.copy')}
                    aria-label={t('ai.copy')}
                  >
                    {copiedSummary ? <Check size={13} className="text-[#00e5ff]" /> : <Copy size={13} />}
                    <span>{copiedSummary ? t('ai.copied') : t('ai.copy')}</span>
                  </button>
                </div>
                <p className="text-sm text-[#e5e2e1] leading-relaxed">
                  {explanation ? pickName(lang, explanation.summary, explanation.summary_ar) : ''}
                </p>
                <div className="pt-1 flex items-center justify-between flex-wrap gap-2">
                  <ModelBadge modelUsed={explanation?.model_used || explanation?.model} provider={explanation?.provider} />
                </div>
              </section>

              {/* Rule-based notice when fallback */}
              {(explanation?.provider === 'rule_based' || explanation?.is_fallback || explanation?.fallback_reason) && (
                <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5 text-amber-400" />
                  <p className="leading-relaxed">{t('ai.ruleBasedNotice')}</p>
                </div>
              )}

              {/* Likely Causes */}
              {((explanation?.likely_causes && explanation.likely_causes.length > 0) ||
                (explanation?.likely_causes_ar && explanation.likely_causes_ar.length > 0)) && (
                <section className="panel p-4 space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#bac9cc]">
                    <AlertTriangle size={15} className="text-[#ffeb3b]" />
                    <span>{t('ai.likelyCauses')}</span>
                  </div>
                  <ul className="space-y-2 text-xs text-[#bac9cc]">
                    {(lang === 'ar' && explanation?.likely_causes_ar?.length
                      ? explanation.likely_causes_ar
                      : explanation?.likely_causes || []
                    ).map((cause, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#ffeb3b] mt-1.5 shrink-0" />
                        <span className="leading-relaxed">{cause}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Recommended Steps */}
              {((explanation?.steps && explanation.steps.length > 0) ||
                (explanation?.steps_ar && explanation.steps_ar.length > 0)) && (
                <section className="panel p-4 space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#bac9cc]">
                    <Wrench size={15} className="text-[#00e5ff]" />
                    <span>{t('ai.steps')}</span>
                  </div>
                  <ol className="space-y-2.5 text-xs text-[#e5e2e1]">
                    {(lang === 'ar' && explanation?.steps_ar?.length
                      ? explanation.steps_ar
                      : explanation?.steps || []
                    ).map((step, idx) => (
                      <li key={idx} className="flex items-start gap-2.5 bg-black/20 p-2 rounded-lg border border-white/5">
                        <span className="w-5 h-5 rounded-full bg-[#00e5ff]/15 text-[#00e5ff] font-bold font-mono text-[11px] flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <span className="leading-relaxed pt-0.5">{step}</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {/* Safety Note */}
              {(explanation?.safety_note || explanation?.safety_note_ar) && (
                <section className="p-3.5 rounded-xl bg-[#ff5449]/10 border border-[#ff5449]/30 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#ffb4ab]">
                    <ShieldAlert size={16} />
                    <span>{t('ai.safetyNote')}</span>
                  </div>
                  <p className="text-xs text-[#ffb4ab] leading-relaxed">
                    {pickName(lang, explanation.safety_note, explanation.safety_note_ar)}
                  </p>
                </section>
              )}

              {/* Disclaimer */}
              <div className="text-[11px] text-[#849396] text-center px-2 py-1 leading-normal italic">
                {t('ai.disclaimer')}
              </div>

              {/* Follow-up chat thread */}
              {chatMessages.length > 0 && (
                <div className="space-y-3 pt-2 border-t border-white/10">
                  {chatMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex flex-col ${
                        msg.role === 'user'
                          ? isRtl ? 'items-start' : 'items-end'
                          : isRtl ? 'items-end' : 'items-start'
                      }`}
                    >
                      <div
                        className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                          msg.role === 'user'
                            ? 'bg-[#00e5ff]/20 text-[#e5e2e1] border border-[#00e5ff]/30'
                            : 'panel text-[#bac9cc] border-white/10'
                        }`}
                      >
                        {msg.content}
                      </div>
                      {msg.role === 'assistant' && (
                        <div className="w-full flex items-center justify-between gap-2 mt-1 px-1">
                          <ModelBadge modelUsed={msg.model_used || msg.model} provider={msg.provider} />
                          <button
                            type="button"
                            onClick={() => handleCopyText(msg.content, false, idx)}
                            className="flex items-center gap-1 text-[10px] text-[#849396] hover:text-[#e5e2e1] p-1 rounded hover:bg-white/10"
                            title={t('ai.copy')}
                            aria-label={t('ai.copy')}
                          >
                            {copiedChatIdx === idx ? <Check size={12} className="text-[#00e5ff]" /> : <Copy size={12} />}
                            <span>{copiedChatIdx === idx ? t('ai.copied') : t('ai.copy')}</span>
                          </button>
                        </div>
                      )}
                      {msg.role === 'assistant' && (msg.provider === 'rule_based' || msg.is_fallback || msg.fallback_reason) && (
                        <div className="flex items-start gap-1.5 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] mt-1 max-w-[85%]">
                          <AlertTriangle size={13} className="shrink-0 mt-0.5 text-amber-400" />
                          <span>{t('ai.ruleBasedNotice')}</span>
                        </div>
                      )}
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex items-center justify-between p-2 rounded-xl bg-white/5 border border-white/5 text-xs">
                      <div className="flex items-center gap-2 text-[#849396]">
                        <div className="w-3.5 h-3.5 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
                        <span>{lang === 'ar' ? `جاري التفكير... (${chatElapsedSec} ث)` : `Thinking... (${chatElapsedSec}s)`}</span>
                      </div>
                      <button
                        type="button"
                        onClick={handleCancelChat}
                        className="text-[11px] text-[#ffb4ab] hover:underline flex items-center gap-1"
                      >
                        <XCircle size={13} />
                        <span>{t('ai.cancel')}</span>
                      </button>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>
              )}
            </>
          )}
        </div>

        {/* Follow-up question input */}
        <form
          onSubmit={handleSendFollowUp}
          className="p-3 border-t border-white/10 bg-[#161618] flex items-center gap-2"
        >
          <input
            type="text"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            placeholder={t('ai.askFollowUp')}
            disabled={loading || chatLoading}
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-[#e5e2e1] placeholder-[#849396] focus:outline-none focus:border-[#00e5ff] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputQuestion.trim() || loading || chatLoading}
            className="p-2 rounded-xl bg-[#00e5ff] text-[#0e0e0e] hover:bg-[#00e5ff]/90 disabled:opacity-40 transition-colors"
            title={t('ai.send')}
            aria-label={t('ai.send')}
          >
            {chatLoading ? (
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
            ) : (
              <Send size={16} className={isRtl ? 'rotate-180' : ''} />
            )}
          </button>
        </form>
      </div>
    </>
  );
}
