/** Settings → Users (owner's layout: a list with a side drawer). Admin only. */
import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import type { UserRole } from '@algaroshy/contracts';
import { apiFetch } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { useT, type MsgKey } from '../../lib/i18n';
import { userProblem } from '../../lib/userText';
import Drawer from '../Drawer';

interface UserRow {
  id: string;
  username: string;
  name: string;
  role: UserRole;
  is_active: boolean;
}

const ROLES: UserRole[] = ['owner_admin', 'operator', 'viewer'];
const field =
  'mt-1 w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-sm text-[#e5e2e1] focus:border-[#00e5ff] focus:outline-none';

export default function UsersTab() {
  const { t, isRtl } = useT();
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<UserRow | 'new' | null>(null);
  const [tick, setTick] = useState(0);
  const Chevron = isRtl ? ChevronLeft : ChevronRight;

  useEffect(() => {
    let live = true;
    apiFetch<UserRow[]>('/api/v1/users')
      .then((rows) => {
        if (!live) return;
        setUsers(rows);
        setFailed(false);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [tick]);

  return (
    <div className="space-y-3" data-testid="users-tab">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-[#bac9cc]">{t('users.intro')}</p>
        <button
          type="button"
          onClick={() => setOpen('new')}
          className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#00e5ff]/15 text-[#00e5ff] text-xs font-bold"
        >
          <Plus size={14} /> {t('users.add')}
        </button>
      </div>
      {failed && (
        <div role="alert" className="panel p-4 text-sm flex items-center justify-between gap-3">
          <span>{t('common.loadFailed')}</span>
          <button type="button" onClick={() => setTick((n) => n + 1)} className="underline text-xs">
            {t('common.retry')}
          </button>
        </div>
      )}
      {!users && !failed && <p className="text-sm text-[#849396]">{t('common.loading')}</p>}
      {users && (
        <ul className="panel divide-y divide-white/5">
          {users.map((u) => (
            <li key={u.id}>
              <button
                type="button"
                onClick={() => setOpen(u)}
                className="w-full grid grid-cols-[1fr_auto_auto] sm:grid-cols-[2fr_1.5fr_1.5fr_1fr_auto] items-center gap-x-3 gap-y-1 p-3 text-start hover:bg-white/5"
              >
                <span className={`text-sm font-bold truncate ${u.is_active ? '' : 'text-[#849396]'}`}>{u.name}</span>
                <bdi dir="ltr" className="hidden sm:block text-xs font-mono text-[#849396] truncate">
                  {u.username}
                </bdi>
                <span className="text-xs text-[#bac9cc] truncate">{t(`role.${u.role}` as MsgKey)}</span>
                <span className={`hidden sm:block text-xs ${u.is_active ? 'text-[#7ee787]' : 'text-[#849396]'}`}>
                  {u.is_active ? `● ${t('users.active')}` : `○ ${t('users.disabled')}`}
                </span>
                <Chevron size={16} className="text-[#849396]" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && (
        <UserDrawer
          key={open === 'new' ? 'new' : open.id}
          user={open === 'new' ? null : open}
          onClose={() => setOpen(null)}
          onSaved={() => {
            setOpen(null);
            setTick((n) => n + 1);
          }}
        />
      )}
    </div>
  );
}

function UserDrawer({ user, onClose, onSaved }: { user: UserRow | null; onClose: () => void; onSaved: () => void }) {
  const { t } = useT();
  const { user: me, logout } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [username, setUsername] = useState(user?.username ?? '');
  const [role, setRole] = useState<UserRole>(user?.role ?? 'operator');
  const [password, setPassword] = useState('');
  const [confirmOff, setConfirmOff] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const self = user !== null && user.id === me?.id;

  const send = async (body: Record<string, unknown>) => {
    setBusy(true);
    setProblem(null);
    try {
      await apiFetch(user ? `/api/v1/users/${user.id}` : '/api/v1/users', {
        method: user ? 'PATCH' : 'POST',
        body: JSON.stringify(body),
      });
      // changing your own password or role ends this sign-in too
      if (self && (body.password || (body.role && body.role !== user.role) || body.is_active === false)) logout();
      else onSaved();
    } catch (err) {
      setProblem(userProblem(err));
      setBusy(false);
    }
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    void send(
      user
        ? { name, username, role, ...(password ? { password } : {}) }
        : { name, username, role, password },
    );
  };

  return (
    <Drawer title={t(user ? 'users.edit' : 'users.new')} onClose={onClose}>
      <form onSubmit={save} className="space-y-4">
        <label className="block text-xs font-bold text-[#bac9cc]">
          {t('users.name')}
          <input className={field} value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
        </label>
        <label className="block text-xs font-bold text-[#bac9cc]">
          {t('users.username')}
          <input
            className={field}
            dir="ltr"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            maxLength={50}
            autoCapitalize="none"
            autoComplete="off"
          />
          <span className="mt-1 block text-[11px] font-normal text-[#849396]">{t('users.usernameHelp')}</span>
        </label>
        <label className="block text-xs font-bold text-[#bac9cc]">
          {t('users.role')}
          <select className={field} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`role.${r}` as MsgKey)}
              </option>
            ))}
          </select>
          <span className="mt-1 block text-[11px] font-normal text-[#849396]">{t(`users.can.${role}` as MsgKey)}</span>
        </label>
        <label className="block text-xs font-bold text-[#bac9cc]">
          {t(user ? 'users.newPassword' : 'users.password')}
          <input
            className={field}
            dir="ltr"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!user}
            minLength={8}
            autoComplete="new-password"
          />
          <span className="mt-1 block text-[11px] font-normal text-[#849396]">
            {t(user ? 'users.newPasswordHelp' : 'users.passwordHelp')}
          </span>
        </label>
        {problem && (
          <p role="alert" className="text-sm text-[#ffb4ab]">
            {problem}
          </p>
        )}
        <button type="submit" disabled={busy} className="w-full py-2.5 rounded-xl bg-[#00e5ff] text-[#0e0e0e] text-sm font-bold disabled:opacity-50">
          {t('settings.save')}
        </button>
        {user && !user.is_active && (
          <button type="button" disabled={busy} onClick={() => send({ is_active: true })} className="w-full py-2.5 rounded-xl border border-[#7ee787]/50 text-[#7ee787] text-sm font-bold disabled:opacity-50">
            {t('users.enable')}
          </button>
        )}
        {user?.is_active && (
          <button
            type="button"
            disabled={busy}
            onClick={() => (confirmOff ? void send({ is_active: false }) : setConfirmOff(true))}
            className="w-full py-2.5 rounded-xl border border-[#ffb4ab]/50 text-[#ffb4ab] text-sm font-bold disabled:opacity-50"
          >
            {t(confirmOff ? 'users.confirmDisable' : 'users.disable')}
          </button>
        )}
      </form>
    </Drawer>
  );
}
