/** "Change my password", for every signed-in user. */
import { useState } from 'react';
import type { LoginResponse } from '@algaroshy/contracts';
import { apiFetch, session } from '../lib/api';
import { useFarmStore } from '../store/farm';
import { useT } from '../lib/i18n';
import { userProblem } from '../lib/userText';
import Drawer from './Drawer';

const field =
  'mt-1 w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-[#e5e2e1] focus:border-[#00e5ff] focus:outline-none';

export default function PasswordDrawer({ onClose }: { onClose: () => void }) {
  const { t } = useT();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== again) {
      setProblem(t('password.mismatch'));
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const res = await apiFetch<LoginResponse>('/api/v1/auth/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      // the old sign-in ended with the old password: carry on with the new one
      session.set(res.access_token);
      useFarmStore.getState().connect(res.access_token);
      setDone(true);
    } catch (err) {
      setProblem(userProblem(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer title={t('password.title')} onClose={onClose}>
      {done ? (
        <p role="status" className="text-sm text-[#7ee787]">
          {t('password.done')}
        </p>
      ) : (
        <form onSubmit={save} className="space-y-4">
          {(
            [
              ['password.current', current, setCurrent, 'current-password'],
              ['password.new', next, setNext, 'new-password'],
              ['password.again', again, setAgain, 'new-password'],
            ] as const
          ).map(([label, value, set, auto]) => (
            <label key={label} className="block text-xs font-bold text-[#bac9cc]">
              {t(label)}
              <input className={field} dir="ltr" type="password" required minLength={auto === 'new-password' ? 8 : 1} autoComplete={auto} value={value} onChange={(e) => set(e.target.value)} />
            </label>
          ))}
          <p className="text-[11px] text-[#849396]">{t('users.passwordHelp')}</p>
          {problem && (
            <p role="alert" className="text-sm text-[#ffb4ab]">
              {problem}
            </p>
          )}
          <button type="submit" disabled={busy} className="w-full py-2.5 rounded-xl bg-[#00e5ff] text-[#0e0e0e] text-sm font-bold disabled:opacity-50">
            {t('settings.save')}
          </button>
        </form>
      )}
    </Drawer>
  );
}
