export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const INSTALL_STORAGE_KEY = 'farm.installDismissed';

export function isAlreadyInstalled(): boolean {
  if (typeof window === 'undefined') return false;
  const isStandalone = window.matchMedia?.('(display-mode: standalone)').matches;
  const isNavStandalone = (navigator as { standalone?: boolean }).standalone === true;
  return Boolean(isStandalone || isNavStandalone);
}

export function isInstallDismissed(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(INSTALL_STORAGE_KEY) === '1';
}

export function dismissInstallPrompt(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(INSTALL_STORAGE_KEY, '1');
  }
}
