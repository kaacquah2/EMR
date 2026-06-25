"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { AuthTokens, User } from "./types";
import { API_BASE } from "./api-base";
import { createApiClient } from "./api-client";
import { InactivityModal } from "@/components/ui/InactivityModal";
import { clearAllOfflineStores } from "./offline-store";

const AUTH_STORAGE_KEY = "medsync_auth";
/** Legacy hint key — kept only to clear stale localStorage entries from old versions. */
const AUTH_PERSISTENT_HINT = "medsync_auth_persistent";

interface AuthState {
  accessToken: string | null;
  /** Always null — refresh credential lives in the HttpOnly medsync_session cookie. */
  refreshToken: null;
  user: User | null;
  isAuthenticated: boolean;
}

export interface LoginOptions {
  /** Deprecated and ignored. Persistent sessions use the HttpOnly cookie set by the backend. */
  rememberMe?: boolean;
}

/** View-as hospital for super_admin only. Persisted in sessionStorage for the tab. */
const VIEW_AS_STORAGE_KEY = "medsync_view_as";

interface AuthContextValue extends AuthState {
  hydrated: boolean;
  login: (tokens: AuthTokens, options?: LoginOptions) => void;
  logout: () => void;
  setTokens: (tokens: Pick<AuthTokens, "access_token">) => void;
  getAccessToken: () => string | null;
  getRefreshToken: () => null;
  refreshTokens: () => Promise<boolean>;
  updateActivity: () => void;
  viewAsHospitalId: string | null;
  viewAsHospitalName: string | null;
  setViewAs: (id: string | null, name: string | null) => void;
  getViewAsHeader: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const INACTIVITY_MS = 15 * 60 * 1000;
const WARNING_MS = 2 * 60 * 1000;
const WARNING_AT_MS = INACTIVITY_MS - WARNING_MS;

/**
 * Load access_token + user from sessionStorage.
 * Refresh token is intentionally NOT stored — it lives in the HttpOnly cookie.
 */
function loadStoredAuth(): Partial<AuthState> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as {
      access_token?: string;
      user_profile?: User;
    };
    if (data.access_token) {
      return {
        accessToken: data.access_token,
        refreshToken: null,
        user: data.user_profile ?? null,
        isAuthenticated: true,
      };
    }
  } catch {
    /* ignore */
  }
  return null;
}

/**
 * Persist access_token + user profile. Refresh token is NOT saved —
 * it lives exclusively in the HttpOnly medsync_session cookie.
 */
function saveStoredAuth(state: AuthState) {
  if (typeof window === "undefined") return;
  if (state.isAuthenticated && state.accessToken) {
    sessionStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        access_token: state.accessToken,
        user_profile: state.user,
      })
    );
  } else {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
  // Clear stale data from previous versions that stored tokens in localStorage.
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(AUTH_PERSISTENT_HINT);
}

/**
 * Try to restore session from the HttpOnly cookie via the refresh-cookie endpoint.
 * Returns {access_token, user} on success, null on failure.
 */
async function tryRestoreFromCookie(): Promise<{ access_token: string; user: User | null }| null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh-cookie`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    const data = await res.json() as { access_token?: string };
    if (!data.access_token) return null;
    // Fetch user profile using the new token
    const meRes = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    const user = meRes.ok ? (await meRes.json() as User) : null;
    return { access_token: data.access_token, user };
  } catch {
    return null;
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

  // Hydration: restore session from sessionStorage, then fall back to HttpOnly cookie.
  useEffect(() => {
    lastActivityRef.current = Date.now();
    (async () => {
      const stored = loadStoredAuth();
      if (stored?.accessToken) {
        setState({
          accessToken: stored.accessToken,
          refreshToken: null,
          user: stored.user ?? null,
          isAuthenticated: true,
        });
        setHydrated(true);
        return;
      }
      // No sessionStorage data — try the HttpOnly cookie (survives page refresh).
      const restored = await tryRestoreFromCookie();
      if (restored) {
        const next: AuthState = {
          accessToken: restored.access_token,
          refreshToken: null,
          user: restored.user,
          isAuthenticated: true,
        };
        setState(next);
        saveStoredAuth(next);
        if (typeof window !== "undefined" && restored.user?.role) {
          const maxAge = 8 * 60 * 60;
          document.cookie = `medsync_session=1; path=/; max-age=${maxAge}; SameSite=Strict; Secure`;
          document.cookie = `medsync_role=${restored.user.role}; path=/; max-age=${maxAge}; SameSite=Strict; Secure`;
        }
      }
      setHydrated(true);
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If we have an access_token but no user profile, fetch it.
  useEffect(() => {
    if (!hydrated || !state.accessToken || state.user) return;
    let cancelled = false;
    (async () => {
      try {
        const apiClient = createApiClient(
          () => state.accessToken,
          async () => {
            // Inline refresh using cookie (no stored refresh_token).
            try {
              const res = await fetch(`${API_BASE}/auth/refresh-cookie`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
              });
              const data = await res.json() as { access_token?: string };
              if (!res.ok || !data.access_token) return false;
              setState((s) => {
                const next = { ...s, accessToken: data.access_token! };
                saveStoredAuth(next);
                return next;
              });
              return true;
            } catch {
              return false;
            }
          },
          () => { lastActivityRef.current = Date.now(); },
          getViewAsHeader
        );
        const profile = await apiClient.get<User>("/auth/me");
        if (cancelled) return;
        setState((s) =>
          s.accessToken === state.accessToken && !s.user
            ? { ...s, user: profile, isAuthenticated: true }
            : s
        );
        // Update user in sessionStorage.
        if (typeof window !== "undefined") {
          const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
          if (raw) {
            try {
              const data = JSON.parse(raw) as Record<string, unknown>;
              sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ ...data, user_profile: profile }));
            } catch { /* ignore */ }
          }
        }
      } catch (err) {
        if (cancelled) return;
        const error = err as { statusCode?: number; detail?: { error?: string } };
        const is401 = error?.statusCode === 401;
        const isNetworkError = error?.detail?.error === "TIMEOUT_OR_ABORT";
        if (is401 || isNetworkError) {
          sessionStorage.removeItem(AUTH_STORAGE_KEY);
          setState({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
          if (typeof window !== "undefined") window.location.href = "/login";
        }
      }
    })();
    return () => { cancelled = true; };
  }, [hydrated, state.accessToken, state.user, getViewAsHeader]);

  const logout = useCallback(async () => {
    const accessToken = state.accessToken;
    setState({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
    warningShownRef.current = false;
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      sessionStorage.removeItem(VIEW_AS_STORAGE_KEY);
      localStorage.removeItem(AUTH_STORAGE_KEY);
      localStorage.removeItem(AUTH_PERSISTENT_HINT);
      try {
        if (accessToken) {
          await fetch(`${API_BASE}/auth/logout`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          });
        }
        // Revoke the HttpOnly cookie session.
        await fetch(`${API_BASE}/auth/logout-cookie`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
        });
      } catch {
        /* ignore */
      }
      document.cookie = "medsync_session=; path=/; max-age=0";
      document.cookie = "medsync_role=; path=/; max-age=0";
      void clearAllOfflineStores();
      window.location.href = "/login";
    }
  }, [state.accessToken]);

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

  const login = useCallback((tokens: AuthTokens, _options?: LoginOptions) => {
    // Only store the access_token. The refresh credential is the HttpOnly cookie
    // set by the backend on /auth/login — never accessible to JavaScript.
    const next: AuthState = {
      accessToken: tokens.access_token,
      refreshToken: null,
      user: tokens.user_profile,
      isAuthenticated: true,
    };
    setState(next);
    if (typeof window !== "undefined") {
      saveStoredAuth(next);
      const maxAge = 8 * 60 * 60;
      document.cookie = `medsync_session=1; path=/; max-age=${maxAge}; SameSite=Strict; Secure`;
      if (tokens.user_profile?.role) {
        document.cookie = `medsync_role=${tokens.user_profile.role}; path=/; max-age=${maxAge}; SameSite=Strict; Secure`;
      }
    }
  }, []);

  const setTokens = useCallback((tokens: Pick<AuthTokens, "access_token">) => {
    setState((s) => {
      const next = { ...s, accessToken: tokens.access_token };
      saveStoredAuth(next);
      return next;
    });
  }, []);

  const getAccessToken = useCallback(() => state.accessToken, [state.accessToken]);
  const getRefreshToken = useCallback((): null => null, []);

  /**
   * Refresh the access token using the HttpOnly medsync_session cookie.
   * Called automatically by the API client on 401 responses.
   */
  const refreshTokens = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh-cookie`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json() as { access_token?: string };
      if (!res.ok || !data.access_token) {
        logout();
        return false;
      }
      setState((s) => {
        const next = { ...s, accessToken: data.access_token! };
        saveStoredAuth(next);
        return next;
      });
      return true;
    } catch {
      logout();
      return false;
    }
  }, [logout]);

  useEffect(() => {
    if (!hydrated) return;
    saveStoredAuth(state);
  }, [hydrated, state]);

  const handleStayLoggedIn = useCallback(() => {
    lastActivityRef.current = Date.now();
    warningShownRef.current = false;
    setShowInactivityWarning(false);
  }, []);

  const value: AuthContextValue = useMemo(
    () => ({
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
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state, hydrated, viewAs.id, viewAs.name]
  );

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
