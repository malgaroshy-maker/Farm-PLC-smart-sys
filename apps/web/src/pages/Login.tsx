import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Languages } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { ApiError } from '../lib/api';
import { useI18nStore, useT } from '../lib/i18n';

export default function Login() {
  const navigate = useNavigate();
  const { user, login } = useAuth();
  const { t } = useT();
  const toggleLang = useI18nStore((s) => s.toggle);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t('login.denied') : t('login.unreachable'));
    } finally {
      setBusy(false);
    }
  };

  const input =
    'w-full bg-[#0e0e0e] border border-[#353534] rounded-lg p-3 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff] transition-colors';

  return (
    <div
      className="min-h-dvh text-[#e5e2e1] flex items-center justify-center p-4 bg-[#0e0e0e] bg-cover bg-center"
      style={{ backgroundImage: 'linear-gradient(rgba(14,14,14,0.82), rgba(14,14,14,0.92)), url(/map/tex_pomegranate.webp)' }}
    >
      <button
        onClick={toggleLang}
        className="fixed top-4 end-4 flex items-center gap-2 px-3 py-2 rounded-lg border border-[#353534] bg-[#1c1b1b]/80 text-sm text-[#bac9cc] hover:text-[#e5e2e1]"
      >
        <Languages size={16} /> {t('common.lang')}
      </button>

      <div className="w-full max-w-sm bg-[#1c1b1b]/95 border border-[#353534] rounded-2xl p-8 shadow-2xl backdrop-blur">
        <div className="flex flex-col items-center mb-8 text-center">
          <img src="/map/logo.webp" alt="" className="w-20 h-20 object-contain mb-3" />
          <h1 className="text-2xl font-bold">{t('app.name')}</h1>
          <p className="text-sm text-[#849396] mt-1">{t('app.tagline')}</p>
        </div>

        {error && (
          <div role="alert" className="mb-5 p-3 rounded-lg bg-[#ffb4ab]/10 border border-[#ffb4ab] text-[#ffb4ab] text-sm text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-xs font-bold text-[#bac9cc] mb-1.5">
              {t('login.username')}
            </label>
            <input id="username" type="text" autoComplete="username" required dir="ltr" className={input} value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs font-bold text-[#bac9cc] mb-1.5">
              {t('login.password')}
            </label>
            <input id="password" type="password" autoComplete="current-password" required dir="ltr" className={input} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button type="submit" disabled={busy} className="w-full bg-[#00e5ff] hover:bg-[#00c9e0] disabled:opacity-60 text-[#0e0e0e] font-bold py-3 rounded-lg transition-colors mt-2">
            {busy ? t('login.busy') : t('login.submit')}
          </button>
        </form>
      </div>
    </div>
  );
}
