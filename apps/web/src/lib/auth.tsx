import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser, LoginResponse, UserRole } from '@algaroshy/contracts';
import { ApiError, apiFetch, session } from './api';

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  can: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(Boolean(session.token));

  // Restore the session from a stored token.
  // Only a 401 ends the session (apiFetch clears the token then). A slow or unreachable
  // server must not sign the owner out: keep the token and retry (G6 fix).
  useEffect(() => {
    if (!session.token) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const attempt = (n: number) => {
      apiFetch<AuthUser>('/api/v1/auth/me')
        .then((u) => {
          if (!live) return;
          setUser(u);
          setLoading(false);
        })
        .catch((e) => {
          if (!live) return;
          if ((e instanceof ApiError && e.status === 401) || !session.token) {
            setLoading(false);
            return;
          }
          timer = setTimeout(() => attempt(n + 1), Math.min(1000 * 2 ** n, 15_000));
        });
    };
    attempt(0);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const off = session.onUnauthorized(() => setUser(null));
    return () => {
      off();
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiFetch<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    session.set(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    session.set(null);
    setUser(null);
  }, []);

  const can = useCallback((...roles: UserRole[]) => !!user && roles.includes(user.role), [user]);

  const value = useMemo(() => ({ user, loading, login, logout, can }), [user, loading, login, logout, can]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
