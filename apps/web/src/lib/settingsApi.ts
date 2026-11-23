/** Settings page API calls (Milestone G3): feature switches, notifications, phone push, zones. */
import type { Zone } from '@algaroshy/contracts';
import { apiFetch } from './api';
import { refreshFeatures } from './features';
import { refreshPoll } from './poll';
import { ZONES_PATH } from './zones';

export async function setFeature(key: string, enabled: boolean): Promise<void> {
  await apiFetch(`/api/v1/system/features/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  });
  refreshFeatures();
}

export interface NotificationStatus {
  in_app: { enabled: boolean; configured: boolean };
  telegram: { enabled: boolean; configured: boolean; token_set: boolean; chat_id: string | null };
  web_push: { enabled: boolean; configured: boolean; devices: number };
  severities: string[];
}

export const fetchNotificationStatus = () => apiFetch<NotificationStatus>('/api/v1/system/notifications');
export const detectTelegramChat = () =>
  apiFetch<{ chat_id: string }>('/api/v1/system/notifications/telegram/detect', { method: 'POST' });
export const saveTelegramChat = (chat_id: string) =>
  apiFetch<{ chat_id: string | null }>('/api/v1/system/notifications/telegram', {
    method: 'PUT',
    body: JSON.stringify({ chat_id }),
  });
export const sendTestNotification = () =>
  apiFetch<{ result: Record<string, unknown> }>('/api/v1/system/notifications/test', { method: 'POST' });

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export type PushResult = 'ok' | 'unsupported' | 'insecure' | 'denied' | 'error';

/** Subscribe THIS device to phone/desktop push. Needs HTTPS (or localhost). */
export async function enablePushOnThisDevice(): Promise<PushResult> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return 'unsupported';
  if (!window.isSecureContext) return 'insecure';
  const perm = await Notification.requestPermission();
  if (perm !== 'granted') return 'denied';
  try {
    const reg = await navigator.serviceWorker.ready;
    const { public_key } = await apiFetch<{ public_key: string }>('/api/v1/system/push/public-key');
    const sub =
      (await reg.pushManager.getSubscription()) ??
      (await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
      }));
    await apiFetch('/api/v1/system/push/subscribe', { method: 'POST', body: JSON.stringify(sub.toJSON()) });
    return 'ok';
  } catch {
    return 'error';
  }
}

export async function updateZone(id: string, patch: Partial<Zone>): Promise<Zone> {
  const z = await apiFetch<Zone>(`/api/v1/zones/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
  refreshPoll(ZONES_PATH);
  return z;
}

export interface NewZone {
  code: string;
  name: string;
  name_ar: string;
  crop_type: Zone['crop_type'];
  area_ha: number;
  max_runtime_min: number;
  default_duration_min: number;
}

export async function createZone(body: NewZone): Promise<Zone> {
  const z = await apiFetch<Zone>('/api/v1/zones', { method: 'POST', body: JSON.stringify(body) });
  refreshPoll(ZONES_PATH);
  return z;
}
