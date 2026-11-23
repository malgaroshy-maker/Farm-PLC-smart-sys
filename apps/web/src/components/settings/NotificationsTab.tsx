/** Notification channels: in-app, Telegram, phone push. Sends S3 critical + S2 major alarms and the daily briefing. */
import { useEffect, useState } from 'react';
import { BellRing, MessageCircle, Smartphone } from 'lucide-react';
import { ApiError } from '../../lib/api';
import { useT, type MsgKey } from '../../lib/i18n';
import {
  detectTelegramChat,
  enablePushOnThisDevice,
  fetchNotificationStatus,
  saveTelegramChat,
  sendTestNotification,
  setFeature,
  type NotificationStatus,
} from '../../lib/settingsApi';
import { Switch } from './FeaturesTab';

export default function NotificationsTab() {
  const { t } = useT();
  const [s, setS] = useState<NotificationStatus | null>(null);
  const [chat, setChat] = useState('');
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const st = await fetchNotificationStatus();
      setS(st);
      setChat(st.telegram.chat_id ?? '');
    } catch {
      setMsg({ text: t('settings.loadFailed'), ok: false });
    }
  };
  useEffect(() => {
    const id = setTimeout(() => void load(), 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const act = async (fn: () => Promise<unknown>, okKey: MsgKey) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ text: t(okKey), ok: true });
      await load();
    } catch (e) {
      const detail = e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? '') : '';
      setMsg({ text: t((`notify.err.${detail}` as MsgKey)) !== `notify.err.${detail}` ? t(`notify.err.${detail}` as MsgKey) : t('settings.saveFailed'), ok: false });
    } finally {
      setBusy(false);
    }
  };

  if (!s) return <div className="text-sm text-[#849396]">{msg?.text ?? t('common.loading')}</div>;

  const toggle = (key: string, on: boolean) => act(() => setFeature(key, on), 'settings.saved');

  return (
    <div className="space-y-4 max-w-2xl" data-testid="notifications-tab">
      <p className="text-xs text-[#bac9cc]">{t('notify.what')}</p>

      <section className="panel p-4 space-y-2">
        <div className="flex items-center gap-2">
          <BellRing size={18} className="text-[#00e5ff]" />
          <h2 className="text-sm font-bold flex-1">{t('notify.inApp')}</h2>
          <Switch on={s.in_app.enabled} onChange={(v) => toggle('notify.in_app', v)} label={t('notify.inApp')} disabled={busy} />
        </div>
        <p className="text-[11px] text-[#849396]">{t('notify.inApp.desc')}</p>
      </section>

      <section className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <MessageCircle size={18} className="text-[#00e5ff]" />
          <h2 className="text-sm font-bold flex-1">{t('notify.telegram')}</h2>
          <Switch on={s.telegram.enabled} onChange={(v) => toggle('notify.telegram', v)} label={t('notify.telegram')} disabled={busy} />
        </div>
        {!s.telegram.token_set ? (
          <ol className="text-[11px] text-[#bac9cc] list-decimal ps-5 space-y-1">
            <li>{t('notify.tg.step1')}</li>
            <li>{t('notify.tg.step2')}</li>
            <li>{t('notify.tg.step3')}</li>
          </ol>
        ) : (
          <div className="space-y-2">
            <p className="text-[11px] text-[#bac9cc]">{t('notify.tg.startHint')}</p>
            <div className="flex flex-wrap gap-2 items-center">
              <button disabled={busy} onClick={() => act(detectTelegramChat, 'notify.tg.detected')} className="px-3 py-1.5 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-xs font-bold">
                {t('notify.tg.detect')}
              </button>
              <input
                value={chat}
                onChange={(e) => setChat(e.target.value)}
                placeholder={t('notify.tg.chatId')}
                aria-label={t('notify.tg.chatId')}
                dir="ltr"
                className="bg-black/30 border border-white/10 rounded-lg px-2 py-1.5 text-xs font-mono w-40"
              />
              <button disabled={busy} onClick={() => act(() => saveTelegramChat(chat), 'settings.saved')} className="px-3 py-1.5 rounded-lg border border-white/10 text-xs">
                {t('settings.save')}
              </button>
            </div>
            <p className="text-[11px]" style={{ color: s.telegram.configured ? '#00e5ff' : '#ffb300' }}>
              {t(s.telegram.configured ? 'notify.ready' : 'notify.tg.needChat')}
            </p>
          </div>
        )}
      </section>

      <section className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Smartphone size={18} className="text-[#00e5ff]" />
          <h2 className="text-sm font-bold flex-1">{t('notify.push')}</h2>
          <Switch on={s.web_push.enabled} onChange={(v) => toggle('notify.web_push', v)} label={t('notify.push')} disabled={busy} />
        </div>
        <p className="text-[11px] text-[#bac9cc]">{t('notify.push.devices')} <bdi className="font-mono">{s.web_push.devices}</bdi></p>
        <button
          disabled={busy}
          onClick={() =>
            act(async () => {
              const r = await enablePushOnThisDevice();
              if (r !== 'ok') throw new Error(r);
            }, 'notify.push.enabled').catch(() => undefined)
          }
          className="px-3 py-1.5 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-xs font-bold"
          data-testid="push-enable"
        >
          {t('notify.push.enableHere')}
        </button>
        {!window.isSecureContext && <p className="text-[11px] text-[#ffb300]">{t('notify.push.httpsNote')}</p>}
      </section>

      <div className="flex items-center gap-3">
        <button disabled={busy} onClick={() => act(sendTestNotification, 'notify.testSent')} className="px-4 py-2 rounded-xl bg-[#00e5ff] text-[#0e0e0e] text-sm font-bold">
          {t('notify.sendTest')}
        </button>
        {msg && (
          <span role="status" className="text-xs" style={{ color: msg.ok ? '#00e5ff' : '#ff5449' }}>
            {msg.text}
          </span>
        )}
      </div>
    </div>
  );
}
