import { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { useT } from '../lib/i18n';
import {
  type BeforeInstallPromptEvent,
  dismissInstallPrompt,
  isAlreadyInstalled,
  isInstallDismissed,
} from '../lib/installPrompt';

export default function InstallPrompt() {
  const { t } = useT();
  const [promptEvent, setPromptEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState<boolean>(() => isInstallDismissed());
  const [installed, setInstalled] = useState<boolean>(() => isAlreadyInstalled());

  useEffect(() => {
    if (installed || dismissed) return;

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setPromptEvent(e as BeforeInstallPromptEvent);
    };

    const handleAppInstalled = () => {
      setInstalled(true);
      setPromptEvent(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, [installed, dismissed]);

  const handleInstallClick = async () => {
    if (!promptEvent) return;
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    if (choice.outcome === 'accepted') {
      setInstalled(true);
    }
    setPromptEvent(null);
  };

  const handleDismiss = () => {
    dismissInstallPrompt();
    setDismissed(true);
    setPromptEvent(null);
  };

  if (installed || dismissed || !promptEvent) {
    return null;
  }

  return (
    <div
      role="banner"
      aria-label={t('pwa.installBanner')}
      data-testid="pwa-install-banner"
      className="fixed bottom-24 lg:bottom-4 inset-x-2 sm:inset-x-auto sm:end-4 z-30 p-3 sm:px-4 rounded-2xl bg-[#141416]/95 border border-[#00e5ff]/40 shadow-2xl backdrop-blur-xl flex items-center justify-between gap-3 max-w-md"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="p-2 rounded-xl bg-[#00e5ff]/15 text-[#00e5ff] shrink-0">
          <Download size={18} />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-bold text-[#e5e2e1] truncate">{t('pwa.installBanner')}</p>
          <p className="text-[10px] text-[#849396] truncate">{t('app.name')} · {t('app.tagline')}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={handleInstallClick}
          className="px-3 py-1.5 rounded-xl bg-[#00e5ff] text-black text-xs font-bold hover:brightness-110 transition-all flex items-center gap-1"
        >
          {t('pwa.installButton')}
        </button>
        <button
          onClick={handleDismiss}
          aria-label={t('pwa.dismiss')}
          className="p-1.5 rounded-lg text-[#849396] hover:text-[#e5e2e1] hover:bg-white/10 transition-colors"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
