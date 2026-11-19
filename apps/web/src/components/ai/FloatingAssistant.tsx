import { useState, useRef } from 'react';
import { X, Send, Bot, XCircle } from 'lucide-react';
import { useFarmStore } from '../../store/farm';
import { useT, fmtNum } from '../../lib/i18n';
import { sendAiChat, type ChatMessage } from '../../lib/api';
import { AiSparklesIcon, FlowIcon, GaugeIcon, PumpIcon, ZonesIcon } from '../icons/FarmIcons';

export default function FloatingAssistant() {
  const { t, lang, isRtl } = useT();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      role: 'assistant',
      content:
        lang === 'ar'
          ? 'مرحباً بك في المساعد الذكي لمزرعة الجروشي. أنا متصل ببيانات الحساسات، المضخات، الإنذارات والجداول المباشرة. كيف يمكنني مساعدتك؟'
          : 'Welcome to Algaroshy Farm Assistant. I am connected to live sensors, pumps, alarms, and irrigation programs. How can I help you today?',
      provider: 'system',
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const state = useFarmStore((s) => s.state);
  const activeAlarms = state?.active_alarms ?? [];
  const pumps = state?.pumps ?? [];
  const activePumps = pumps.filter((p) => p.state === 'running').length;
  const runningZones = (state?.zones ?? []).filter((z) => z.state === 'running').length;
  const flow = state?.main_flow_m3h ?? 0;
  const pressure = state?.main_pressure_bar ?? 0;

  const quickPrompts = [
    { key: 'chat.quickPrompt.activeZones', text: t('chat.quickPrompt.activeZones') },
    { key: 'chat.quickPrompt.waterYesterday', text: t('chat.quickPrompt.waterYesterday') },
    { key: 'chat.quickPrompt.activeAlarms', text: t('chat.quickPrompt.activeAlarms') },
    { key: 'chat.quickPrompt.weatherForecast', text: t('chat.quickPrompt.weatherForecast') },
  ];

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setLoading(false);
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: t('ai.cancelled'),
        provider: 'rule_based',
        model: 'cancelled',
        is_fallback: true,
        fallback_reason: 'cancelled_by_operator',
        created_at: new Date().toISOString(),
      },
    ]);
    setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const handleSend = async (queryText?: string) => {
    const text = (queryText ?? input).trim();
    if (!text || loading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    if (!queryText) setInput('');
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Build lightweight state payload to provide prompt context even if backend tool lookup is bypassed
      const liveContext = `[Telemetry: P=${pressure.toFixed(2)}bar, Q=${flow.toFixed(1)}m3/h, RunningZones=${runningZones}, ActivePumps=${activePumps}, Alarms=${activeAlarms.length}]`;
      const apiPayload = nextMessages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({
          role: m.role,
          content: m.role === 'user' ? `${m.content}\n${liveContext}` : m.content,
        }));

      const res = await sendAiChat(apiPayload, lang, controller.signal);
      setMessages([
        ...nextMessages,
        {
          role: 'assistant',
          content: res.message,
          provider: res.provider,
          model: res.model,
          is_fallback: res.is_fallback,
          latency_ms: res.latency_ms,
          fallback_reason: res.fallback_reason,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err: unknown) {
      if (controller.signal.aborted) {
        return;
      }

      const errMsg = err instanceof Error ? err.message : (lang === 'ar' ? 'تعذر الاتصال بخدمة الذكاء الاصطناعي' : 'Could not connect to AI assistant');
      setMessages([
        ...nextMessages,
        {
          role: 'assistant',
          content: `${lang === 'ar' ? 'عذراً، تعذر الاتصال بالمساعد الذكي في الوقت الحالي:' : 'Unable to connect to AI assistant:'} ${errMsg}`,
          provider: 'system',
          is_fallback: true,
          fallback_reason: 'connection_error',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  };

  return (
    <>
      {/* Floating Action Button (FAB) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          title={t('chat.title')}
          aria-label={t('chat.title')}
          className="fixed bottom-6 end-6 z-40 p-3.5 rounded-full bg-gradient-to-tr from-[#00e5ff] to-[#00b0ff] text-[#0e0e0e] shadow-[0_4px_20px_rgba(0,229,255,0.4)] hover:shadow-[0_6px_25px_rgba(0,229,255,0.6)] hover:scale-105 transition-all flex items-center justify-center group"
        >
          <AiSparklesIcon size={24} accent="#0e0e0e" className="group-hover:rotate-12 transition-transform" />
          <span className="sr-only">{t('chat.title')}</span>
        </button>
      )}

      {/* Slide-over chat drawer */}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t('chat.title')}
          className="fixed bottom-4 end-4 z-50 w-[420px] max-w-[calc(100vw-2rem)] h-[620px] max-h-[calc(100vh-2rem)] flex flex-col bg-[#141416]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="p-3.5 border-b border-white/10 bg-white/5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-xl bg-[#00e5ff]/15 text-[#00e5ff]">
                <Bot size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#e5e2e1] leading-tight flex items-center gap-1.5">
                  {t('chat.title')}
                  <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-pulse" />
                </h3>
                <span className="text-[11px] text-[#849396]">{t('chat.online')}</span>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              aria-label={t('drawer.close')}
              className="p-1.5 rounded-lg text-[#849396] hover:bg-white/10 hover:text-[#e5e2e1] transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Live Farm Telemetry Badges Bar */}
          <div className="px-3 py-2 bg-black/40 border-b border-white/5 flex items-center justify-between gap-1 overflow-x-auto text-[11px] font-mono">
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 text-[#bac9cc]">
              <GaugeIcon size={14} accent="#00e5ff" />
              <span>{fmtNum(pressure, 2)} bar</span>
            </div>
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 text-[#bac9cc]">
              <FlowIcon size={14} accent="#00e5ff" />
              <span>{fmtNum(flow, 1)} m³/h</span>
            </div>
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 text-[#bac9cc]">
              <PumpIcon size={14} accent={activePumps ? '#00e5ff' : '#849396'} />
              <span>{activePumps} {t('chat.telemetry.pumps')}</span>
            </div>
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 text-[#bac9cc]">
              <ZonesIcon size={14} accent={runningZones ? '#00e5ff' : '#849396'} />
              <span>{runningZones} {t('chat.telemetry.zones')}</span>
            </div>
          </div>

          {/* Messages feed */}
          <div className="flex-1 overflow-y-auto p-3.5 space-y-3">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${
                  m.role === 'user'
                    ? isRtl ? 'items-start' : 'items-end'
                    : isRtl ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-[#00e5ff]/20 text-[#e5e2e1] border border-[#00e5ff]/30'
                      : 'panel text-[#bac9cc] border-white/10'
                  }`}
                >
                  {m.content}
                </div>
                {m.role === 'assistant' && m.provider && m.provider !== 'system' && (
                  <div className="flex items-center gap-1.5 text-[10px] text-[#849396] mt-1 px-1 flex-wrap">
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-white/5">
                      {m.is_fallback ? t('ai.ruleBasedLabel') : m.provider}
                    </span>
                    {!m.is_fallback && (m.model_used || m.model) && (
                      <span className="font-mono text-[#00e5ff] px-1.5 py-0.5 rounded bg-white/5 border border-white/10">
                        {m.model_used || m.model}
                      </span>
                    )}
                    {m.latency_ms !== undefined && m.latency_ms > 0 && (
                      <span className="font-mono text-[#00e5ff]">
                        {m.latency_ms >= 1000
                          ? `${(m.latency_ms / 1000).toFixed(1)} s`
                          : `${m.latency_ms} ms`}
                      </span>
                    )}
                    {m.fallback_reason && (
                      <span className="font-mono px-1.5 py-0.2 rounded bg-[#ff9f43]/15 text-[#ff9f43] border border-[#ff9f43]/30">
                        {m.fallback_reason}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/5 text-xs animate-fadeIn">
                <div className="flex items-center gap-2 text-[#849396]">
                  <div className="w-3.5 h-3.5 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
                  <span>{t('ai.analyzingProgress')}</span>
                </div>
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-[11px] text-[#ffb4ab] hover:underline flex items-center gap-1"
                >
                  <XCircle size={13} />
                  <span>{t('ai.cancel')}</span>
                </button>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Quick Prompt Pills */}
          <div className="px-3 py-2 border-t border-white/5 bg-black/20 flex gap-1.5 overflow-x-auto no-scrollbar">
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(p.text)}
                disabled={loading}
                className="whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] bg-white/5 hover:bg-[#00e5ff]/15 text-[#bac9cc] hover:text-[#00e5ff] border border-white/10 transition-colors shrink-0 disabled:opacity-40"
              >
                {p.text}
              </button>
            ))}
          </div>

          {/* Input form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="p-3 border-t border-white/10 bg-[#161618] flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('chat.inputPlaceholder')}
              disabled={loading}
              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-[#e5e2e1] placeholder-[#849396] focus:outline-none focus:border-[#00e5ff] disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="p-2 rounded-xl bg-[#00e5ff] text-[#0e0e0e] hover:bg-[#00e5ff]/90 disabled:opacity-40 transition-colors"
              title={t('ai.send')}
              aria-label={t('ai.send')}
            >
              <Send size={15} className={isRtl ? 'rotate-180' : ''} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
