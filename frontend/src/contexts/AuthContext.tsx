import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { isLocale, useI18n } from "@/contexts/I18nContext";
import { authApi } from "@/services/api";
import { setSessionExpiredHandler, tokenStore } from "@/services/http";
import { wasRecentlyRevoked } from "@/services/realtime";
import { browserTimeZone, setDisplayTimeZone } from "@/utils/format";
import type { Me, Role } from "@/types/api";

interface AuthValue {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (u: Me) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function homePath(role: Role) {
  if (role === "admin") return "/admin";
  if (role === "methodist") return "/methodist";
  return role === "student" ? "/student" : "/teacher";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<Me | null>(null);
  // Apply the profile time zone synchronously, before anything renders with it.
  const setUser = useCallback((value: Me | null | ((prev: Me | null) => Me | null)) => {
    setUserState((prev) => {
      const next = typeof value === "function" ? value(prev) : value;
      setDisplayTimeZone(next?.timezone);
      return next;
    });
  }, []);
  const [loading, setLoading] = useState(true);
  const loggingOut = useRef(false);
  const qc = useQueryClient();
  const { t, setLocale } = useI18n();

  // First sign-in: the profile has no time zone yet — take the browser's.
  useEffect(() => {
    if (user && !user.timezone) {
      authApi.updateMe({ timezone: browserTimeZone() }).then(setUser).catch(() => undefined);
    }
  }, [user, setUser]);

  const loadUser = useCallback(async () => {
    if (!tokenStore.access && !tokenStore.refresh) {
      setUser(null);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch {
      tokenStore.clear();
      setUser(null);
    }
  }, [setUser]);

  useEffect(() => {
    loadUser().finally(() => setLoading(false));
  }, [loadUser]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      if (loggingOut.current) return; // intentional logout in this tab
      setUser((prev) => {
        if (prev) toast.error(wasRecentlyRevoked() ? t.auth.sessionRevoked : t.auth.sessionExpired);
        return null;
      });
      qc.clear();
    });
  }, [qc, t, setUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login(email, password);
      tokenStore.set(tokens);
      const me = await authApi.me();
      qc.clear();
      setUser(me);
      if (isLocale(me.locale)) setLocale(me.locale);
      return me;
    },
    [qc, setLocale, setUser],
  );

  const logout = useCallback(async () => {
    loggingOut.current = true;
    try {
      await authApi.logout();
    } catch {
      /* token may already be invalid */
    }
    tokenStore.clear();
    qc.clear();
    setUser(null);
    loggingOut.current = false;
  }, [qc, setUser]);

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser: loadUser, setUser }),
    [user, loading, login, logout, loadUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
