import type { ApiError } from "./types";
import { API_BASE } from "./api-base";

const DEFAULT_TIMEOUT_MS = 30_000;

/** Timeouts, our TIMEOUT_OR_ABORT wrapper, or fetch AbortError (navigation / passed signal). */
export function isBenignApiNetworkFailure(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { name?: string; detail?: { error?: string }; statusCode?: number };
  if (e.detail?.error === "TIMEOUT_OR_ABORT") return true;
  if (e.statusCode === 408) return true;
  if (e.name === "AbortError") return true;
  return false;
}

export type RequestOptions = RequestInit & {
  getToken?: () => string | null;
  onRefresh?: () => Promise<boolean>;
  onActivity?: () => void;
  /** When set, add X-View-As-Hospital header (super_admin facility switch). */
  getViewAsHeader?: () => string | null;
  retryCount?: number;
  timeoutMs?: number;
};

function isPublicApiPath(path: string): boolean {
  const p = path.startsWith("/") ? path : `/${path}`;
  return p === "/health" || p.startsWith("/auth/");
}

type RequestSharedOpts = Pick<
  RequestOptions,
  "getToken" | "onRefresh" | "onActivity" | "getViewAsHeader"
>;

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { getToken, onRefresh, onActivity, getViewAsHeader, retryCount = 0, timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...init } = options;
  const sharedOpts: RequestSharedOpts = { getToken, onRefresh, onActivity, getViewAsHeader };
  const token = getToken?.() ?? null;
  const viewAsId = getViewAsHeader?.() ?? null;
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const isFormData = init.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(init.headers as Record<string, string>),
  };
  // Avoid sending protected requests without a token during initial auth hydration.
  // Backend will correctly 403, but frontend should treat this as unauthenticated (401)
  // and avoid spamming permission-denied logs / confusing UX.
  if (!token && !isPublicApiPath(path)) {
    const e = new Error("Not authenticated") as Error & { detail?: Record<string, unknown>; statusCode?: number };
    e.detail = { error: "NOT_AUTHENTICATED", message: "Access token is missing" };
    (e as Error & { statusCode: number }).statusCode = 401;
    throw e;
  }
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  if (viewAsId) {
    (headers as Record<string, string>)["X-View-As-Hospital"] = viewAsId;
  }
  let signal: AbortSignal | undefined = callerSignal ?? undefined;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  /** Why the linked AbortController fired: timeout vs caller signal (first wins). Pre-aborted callers must be visible in catch. */
  let abortCause: "timeout" | "caller" | null = callerSignal?.aborted ? "caller" : null;
  if (timeoutMs > 0 || callerSignal) {
    const controller = new AbortController();
    signal = controller.signal;
    if (timeoutMs > 0) {
      timeoutId = setTimeout(() => {
        if (abortCause === null) abortCause = "timeout";
        controller.abort();
      }, timeoutMs);
    }
    if (callerSignal) {
      if (callerSignal.aborted) {
        controller.abort();
      } else {
        callerSignal.addEventListener("abort", () => {
          if (abortCause === null) abortCause = "caller";
          controller.abort();
        });
      }
    }
  }
  try {
    const res = await fetch(url, { ...init, headers, signal });
    if (res.status === 401 && onRefresh && getToken && retryCount === 0) {
      const refreshed = await onRefresh();
      if (refreshed) {
        return request<T>(path, {
          ...sharedOpts,
          ...init,
          signal: callerSignal,
          timeoutMs,
          retryCount: 1,
        });
      }
    }
    if (!res.ok) {
      const err: ApiError & Record<string, unknown> = await res.json().catch(() => ({
        error: "UNKNOWN",
        message: res.statusText,
      }));
      const e = new Error(err.message || res.statusText) as Error & { detail?: Record<string, unknown>; statusCode?: number };
      e.detail = err;
      (e as Error & { statusCode: number }).statusCode = res.status;
      throw e;
    }
    onActivity?.();
    if (res.status === 204) return undefined as T;
    return res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      if (abortCause === "caller") {
        throw e;
      }
      const method = (init.method || "GET").toUpperCase();
      // Transient network hiccups are common during local dev startup.
      // Retry idempotent GET once on timeout only (not caller cancellation).
      if (method === "GET" && retryCount === 0 && abortCause === "timeout") {
        return request<T>(path, {
          ...sharedOpts,
          ...init,
          signal: callerSignal,
          timeoutMs,
          retryCount: 1,
        });
      }
      const timeoutErr = new Error("Request timed out or was aborted") as Error & {
        detail?: Record<string, unknown>;
        statusCode?: number;
      };
      timeoutErr.detail = {
        error: "TIMEOUT_OR_ABORT",
        message: e.message,
        path,
        method,
        timeoutMs,
        abortCause: abortCause ?? "unknown",
      };
      timeoutErr.statusCode = 408;
      if (typeof window !== "undefined") window.dispatchEvent(new Event("medsync:apierror"));
      throw timeoutErr;
    }
    if (typeof window !== "undefined" && e instanceof TypeError && e.message === "Failed to fetch") {
      window.dispatchEvent(new Event("medsync:apierror"));
    }
    throw e;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

/** Request for Blob responses (used for file downloads, PDF exports, etc). */
async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const { getToken, onRefresh, onActivity, getViewAsHeader, retryCount = 0, timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...init } = options;
  const sharedOpts: RequestSharedOpts = { getToken, onRefresh, onActivity, getViewAsHeader };
  const token = getToken?.() ?? null;
  const viewAsId = getViewAsHeader?.() ?? null;
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: HeadersInit = {
    ...(init.headers as Record<string, string>),
  };
  if (!token && !isPublicApiPath(path)) {
    const e = new Error("Not authenticated") as Error & { detail?: Record<string, unknown>; statusCode?: number };
    e.detail = { error: "NOT_AUTHENTICATED", message: "Access token is missing" };
    (e as Error & { statusCode: number }).statusCode = 401;
    throw e;
  }
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  if (viewAsId) {
    (headers as Record<string, string>)["X-View-As-Hospital"] = viewAsId;
  }
  let signal: AbortSignal | undefined = callerSignal ?? undefined;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let abortCause: "timeout" | "caller" | null = callerSignal?.aborted ? "caller" : null;
  if (timeoutMs > 0 || callerSignal) {
    const controller = new AbortController();
    signal = controller.signal;
    if (timeoutMs > 0) {
      timeoutId = setTimeout(() => {
        if (abortCause === null) abortCause = "timeout";
        controller.abort();
      }, timeoutMs);
    }
    if (callerSignal) {
      if (callerSignal.aborted) {
        controller.abort();
      } else {
        callerSignal.addEventListener("abort", () => {
          if (abortCause === null) abortCause = "caller";
          controller.abort();
        });
      }
    }
  }
  try {
    const res = await fetch(url, { ...init, headers, signal });
    if (res.status === 401 && onRefresh && getToken && retryCount === 0) {
      const refreshed = await onRefresh();
      if (refreshed) {
        return requestBlob(path, {
          ...sharedOpts,
          ...init,
          signal: callerSignal,
          timeoutMs,
          retryCount: 1,
        });
      }
    }
    if (!res.ok) {
      const err: ApiError & Record<string, unknown> = await res
        .json()
        .catch(() => ({
          error: "UNKNOWN",
          message: res.statusText,
        }));
      const e = new Error(err.message || res.statusText) as Error & { detail?: Record<string, unknown>; statusCode?: number };
      e.detail = err;
      (e as Error & { statusCode: number }).statusCode = res.status;
      throw e;
    }
    onActivity?.();
    return res.blob();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      if (abortCause === "caller") {
        throw e;
      }
      const method = (init.method || "GET").toUpperCase();
      if (method === "GET" && retryCount === 0 && abortCause === "timeout") {
        return requestBlob(path, {
          ...sharedOpts,
          ...init,
          signal: callerSignal,
          timeoutMs,
          retryCount: 1,
        });
      }
      const timeoutErr = new Error("Request timed out or was aborted") as Error & {
        detail?: Record<string, unknown>;
        statusCode?: number;
      };
      timeoutErr.detail = {
        error: "TIMEOUT_OR_ABORT",
        message: e.message,
        path,
        method,
        timeoutMs,
        abortCause: abortCause ?? "unknown",
      };
      timeoutErr.statusCode = 408;
      if (typeof window !== "undefined") window.dispatchEvent(new Event("medsync:apierror"));
      throw timeoutErr;
    }
    if (typeof window !== "undefined" && e instanceof TypeError && e.message === "Failed to fetch") {
      window.dispatchEvent(new Event("medsync:apierror"));
    }
    throw e;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

/** Optional per-request options (e.g. AbortSignal for cancelation, timeout override). */
export type ClientRequestOptions = Pick<RequestOptions, "signal" | "timeoutMs">;

export function createApiClient(
  getToken: () => string | null,
  onRefresh?: () => Promise<boolean>,
  onActivity?: () => void,
  getViewAsHeader?: () => string | null
) {
  const opts = { getToken, onRefresh, onActivity, getViewAsHeader };
  const isClientReqOptions = (v: unknown): v is ClientRequestOptions => {
    if (!v || typeof v !== "object") return false;
    return "signal" in (v as Record<string, unknown>) || "timeoutMs" in (v as Record<string, unknown>);
  };
  return {
    get: <T>(path: string, reqOpts?: ClientRequestOptions) =>
      request<T>(path, { ...opts, ...reqOpts, method: "GET" }),
    post: <T>(path: string, body?: unknown, reqOpts?: ClientRequestOptions) =>
      request<T>(path, {
        ...opts,
        ...reqOpts,
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      }),
    postForm: <T>(path: string, formData: FormData, reqOpts?: ClientRequestOptions) =>
      request<T>(path, {
        ...opts,
        ...reqOpts,
        method: "POST",
        body: formData,
        headers: {},
      }),
    patch: <T>(path: string, body?: unknown, reqOpts?: ClientRequestOptions) =>
      request<T>(path, {
        ...opts,
        ...reqOpts,
        method: "PATCH",
        body: body ? JSON.stringify(body) : undefined,
      }),
    delete: <T>(path: string, bodyOrReqOpts?: unknown, reqOpts?: ClientRequestOptions) => {
      const body = isClientReqOptions(bodyOrReqOpts) ? undefined : bodyOrReqOpts;
      const resolvedReqOpts = isClientReqOptions(bodyOrReqOpts) ? bodyOrReqOpts : reqOpts;
      return request<T>(path, {
        ...opts,
        ...resolvedReqOpts,
        method: "DELETE",
        body: body ? JSON.stringify(body) : undefined,
      });
    },
    getBlob: (path: string, reqOpts?: ClientRequestOptions) =>
      requestBlob(path, { ...opts, ...reqOpts, method: "GET" }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
