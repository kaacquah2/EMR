"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { AuthTokens, User } from "./types";
import { API_BASE } from "./api-base";
import { InactivityModal } from "@/components/ui/InactivityModal";

const AUTH_STORAGE_KEY = "medsync_auth";
/** When set, auth is in localStorage (remember me). When unset, auth is in sessionStorage only. */
const AUTH_PERSISTENT_HINT = "medsync_auth_persistent";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
}

export interface LoginOptions {
  /** ⚠️  DEPRECATED: "Remember me" feature removed for security.
   *  Tokens are now stored in sessionStorage only (cleared on tab close).
   *  For persistent sessions, use HttpOnly cookies via backend (not yet implemented).
   *  See SECURITY NOTE below. */
  rememberMe?: boolean; // Ignored - kept for backward compatibility
}

/** View-as hospital for super_admin only. Persisted in sessionStorage for the tab. */
const VIEW_AS_STORAGE_KEY = "medsync_view_as";

interface AuthContextValue extends AuthState {
  hydrated: boolean;
  login: (tokens: AuthTokens, options?: LoginOptions) => void;
  logout: () => void;
  setTokens: (tokens: Pick<AuthTokens, "access_token" | "refresh_token">) => void;
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  refreshTokens: () => Promise<boolean>;
  updateActivity: () => void;
  /** Super_admin only: view as this hospital (id). Null = all hospitals. */
  viewAsHospitalId: string | null;
  viewAsHospitalName: string | null;
  setViewAs: (id: string | null, name: string | null) => void;
  getViewAsHeader: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const INACTIVITY_MS = 15 * 60 * 1000;
const WARNING_MS = 2 * 60 * 1000;
/** Show warning when this much time has passed without activity (15min - 2min). */
const WARNING_AT_MS = INACTIVITY_MS - WARNING_MS;

function loadStoredAuth(): Partial<AuthState> | null {
  if (typeof window === "undefined") return null;
  try {
    // ⚠️  SECURITY: Only load from sessionStorage (never localStorage)
    // sessionStorage is cleared when the tab/window closes, limiting XSS exposure
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as {
      access_token?: string;
      refresh_token?: string;
      user_profile?: User;
    };
    if (data.access_token) {
      return {
        accessToken: data.access_token,
        refreshToken: data.refresh_token ?? null,
        user: data.user_profile ?? null,
        isAuthenticated: true,
      };
    }
  } catch {
    /* ignore */
  }
  return null;
}

// Second param kept for API compatibility; storage is always sessionStorage for security.
function saveStoredAuth(state: AuthState, _persistent?: boolean) {
  void _persistent;
  if (typeof window === "undefined") return;
  // ⚠️  SECURITY: Always use sessionStorage, never localStorage
  // sessionStorage is automatically cleared when the tab closes
  if (state.isAuthenticated && state.accessToken && state.user) {
    sessionStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        access_token: state.accessToken,
        refresh_token: state.refreshToken,
        user_profile: state.user,
      })
    );
    // Clear any old localStorage data from previous versions
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(AUTH_PERSISTENT_HINT);
  } else {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(AUTH_PERSISTENT_HINT);
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [state, setState] = useState<AuthState>({
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,
  });
  const [viewAs, setViewAsState] = useState<{ id: string | null; name: string | null }>(() => {
    if (typeof window === "undefined") return { id: null, name: null };
    try {
      const raw = sessionStorage.getItem(VIEW_AS_STORAGE_KEY);
      if (raw) {
        const v = JSON.parse(raw) as { id?: string; name?: string };
        if (v.id) return { id: v.id, name: v.name ?? null };
      }
    } catch {
      /* ignore */
    }
    return { id: null, name: null };
  });
  const lastActivityRef = useRef<number>(0);

  const setViewAs = useCallback((id: string | null, name: string | null) => {
    setViewAsState({ id, name });
    if (typeof window !== "undefined") {
      if (id) sessionStorage.setItem(VIEW_AS_STORAGE_KEY, JSON.stringify({ id, name }));
      else sessionStorage.removeItem(VIEW_AS_STORAGE_KEY);
    }
  }, []);

  const getViewAsHeader = useCallback(() => viewAs.id, [viewAs.id]);
  const warningShownRef = useRef(false);
  const [showInactivityWarning, setShowInactivityWarning] = useState(false);

  useEffect(() => {
    lastActivityRef.current = Date.now();
    const stored = loadStoredAuth();
    queueMicrotask(() => {
      if (stored) {
        setState({
          accessToken: stored.accessToken ?? null,
          refreshToken: stored.refreshToken ?? null,
          user: stored.user ?? null,
          isAuthenticated: stored.isAuthenticated ?? false,
        });
      }
      setHydrated(true);
    });
  }, []);

  // If we have a token but no user (e.g. partial storage or stale shape), fetch /auth/me so pages don't stay on "Loading..."
  useEffect(() => {
    if (!hydrated || !state.accessToken || state.user) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${state.accessToken}` },
        });
        if (cancelled) return;
        if (!res.ok) {
          if (res.status === 401) {
            sessionStorage.removeItem(AUTH_STORAGE_KEY);
            setState({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
            if (typeof window !== "undefined") window.location.href = "/login";
          }
          return;
        }
        const profile = await res.json();
        if (cancelled) return;
        setState((s) =>
          s.accessToken === state.accessToken && !s.user
            ? { ...s, user: profile, isAuthenticated: true }
            : s
        );
        if (typeof window !== "undefined") {
          const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
          if (raw) {
            try {
              const data = JSON.parse(raw) as { access_token?: string; refresh_token?: string; user_profile?: unknown };
              sessionStorage.setItem(
                AUTH_STORAGE_KEY,
                JSON.stringify({ ...data, user_profile: profile }),
              );
            } catch {
              /* ignore */
            }
          }
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hydrated, state.accessToken, state.user]);

  const logout = useCallback(async () => {
    const accessToken = state.accessToken;
    const refreshToken = state.refreshToken;
    setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
    warningShownRef.current = false;
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      sessionStorage.removeItem(VIEW_AS_STORAGE_KEY);
      localStorage.removeItem(AUTH_STORAGE_KEY);
      localStorage.removeItem(AUTH_PERSISTENT_HINT);
      if (accessToken) {
        try {
          await fetch(`${API_BASE}/auth/logout`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
            body: refreshToken
              ? JSON.stringify({ refresh_token: refreshToken })
              : undefined,
          });
        } catch {
          /* ignore */
        }
      }
      document.cookie = "medsync_session=; path=/; max-age=0";
      window.location.href = "/login";
    }
  }, [state.accessToken, state.refreshToken]);

  const updateActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
  }, []);

  useEffect(() => {
    if (!state.isAuthenticated) return;
    const check = () => {
      const elapsed = Date.now() - lastActivityRef.current;
      if (elapsed >= INACTIVITY_MS) {
        setShowInactivityWarning(false);
        logout();
      } else if (elapsed >= WARNING_AT_MS && !warningShownRef.current) {
        warningShownRef.current = true;
        setShowInactivityWarning(true);
      }
    };
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, [state.isAuthenticated, logout]);

  useEffect(() => {
    if (!state.isAuthenticated) return;
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    const handler = () => updateActivity();
    events.forEach((e) => window.addEventListener(e, handler));
    return () => events.forEach((e) => window.removeEventListener(e, handler));
  }, [state.isAuthenticated, updateActivity]);

  const login = useCallback((tokens: AuthTokens, options?: LoginOptions) => {
    const next = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      user: tokens.user_profile,
      isAuthenticated: true,
    };
    setState(next);
    if (typeof window !== "undefined") {
      saveStoredAuth(next, options?.rememberMe);
      // HIGH-3 FIX: Add security flags to session cookie (SameSite=Strict; Secure)
      // Note: HttpOnly cannot be set from JavaScript; must be configured on backend via Set-Cookie header
      const maxAge = 8 * 60 * 60; // 8 hours in seconds
      document.cookie = `medsync_session=1; path=/; max-age=${maxAge}; SameSite=Strict; Secure`;
    }
  }, []);

  const setTokens = useCallback(
    (tokens: Pick<AuthTokens, "access_token" | "refresh_token">) => {
      setState((s) => {
        const next = {
          ...s,
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        };
        if (typeof window !== "undefined") saveStoredAuth(next, undefined);
        return next;
      });
    },
    []
  );

  const getAccessToken = useCallback(() => state.accessToken, [state.accessToken]);
  const getRefreshToken = useCallback(() => state.refreshToken, [state.refreshToken]);

  const refreshTokens = useCallback(async (): Promise<boolean> => {
    const refresh = state.refreshToken;
    if (!refresh) {
      logout();
      return false;
    }
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      const data = await res.json();
      if (!res.ok) {
        logout();
        return false;
      }
      setState((s) => {
        const next = {
          ...s,
          accessToken: data.access_token,
          refreshToken: data.refresh_token ?? refresh,
        };
        if (typeof window !== "undefined") saveStoredAuth(next, undefined);
        return next;
      });
      return true;
    } catch {
      logout();
      return false;
    }
  }, [state.refreshToken, logout]);

  useEffect(() => {
    if (!hydrated) return;
    saveStoredAuth(state, undefined);
  }, [hydrated, state]);

  const handleStayLoggedIn = useCallback(() => {
    lastActivityRef.current = Date.now();
    warningShownRef.current = false;
    setShowInactivityWarning(false);
  }, []);

  const value: AuthContextValue = {
    ...state,
    hydrated,
    login,
    logout,
    setTokens,
    getAccessToken,
    getRefreshToken,
    refreshTokens,
    updateActivity,
    viewAsHospitalId: viewAs.id,
    viewAsHospitalName: viewAs.name,
    setViewAs,
    getViewAsHeader,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      <InactivityModal
        open={showInactivityWarning}
        onStayLoggedIn={handleStayLoggedIn}
        onLogout={logout}
      />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
