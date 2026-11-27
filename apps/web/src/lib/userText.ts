import { ApiError } from './api';
import { tr, type MsgKey } from './i18n';

const CODES = [
  'username_invalid',
  'username_taken',
  'password_too_short',
  'password_too_long',
  'name_required',
  'last_admin',
  'user_not_found',
  'wrong_current_password',
];

/** The server's refusal about an account, in the viewer's language. */
export function userProblem(err: unknown): string {
  const message = err instanceof Error ? err.message : '';
  if (CODES.includes(message)) return tr(`users.error.${message}` as MsgKey);
  if (err instanceof ApiError && err.status === 429) return tr('users.error.throttled');
  return tr('common.saveFailed');
}
