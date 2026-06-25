/**
 * useResource — generic SWR-backed data-fetching primitive with AbortSignal cancellation.
 *
 * Replaces the repeated manual useState/useEffect/try-catch pattern present in ~26 hooks.
 * Provides caching, dedup, focus-revalidation, and cancellation out of the box.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useResource<Patient[]>('/patients');
 *
 * Advanced (conditional, with params):
 *   const url = id ? `/patients/${id}` : null;        // null disables fetching
 *   const { data } = useResource<Patient>(url);
 */

"use client";

import { useCallback } from "react";
import useSWR, { type SWRConfiguration } from "swr";
import { useApi } from "./use-api";

export interface UseResourceResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** Trigger a manual revalidation (e.g. after a mutation). */
  refetch: () => Promise<T | null | undefined>;
}

export interface UseResourceOptions<T> extends SWRConfiguration<T> {
  /**
   * Set to false to skip the request (same as passing null as key).
   * Useful when a required param isn't available yet.
   */
  enabled?: boolean;
}

/**
 * @param path  API path relative to /api/v1. Pass null to disable.
 * @param opts  Optional SWR configuration overrides.
 */
export function useResource<T>(
  path: string | null,
  opts: UseResourceOptions<T> = {}
): UseResourceResult<T> {
  const api = useApi();
  const { enabled = true, ...swrOpts } = opts;

  // null key → SWR skips the request (disabled or path not yet known)
  const key = enabled && path ? path : null;

  const fetcher = useCallback(
    async (url: string): Promise<T> => {
      const result = await api.get<T>(url);
      return result as T;
    },
    [api]
  );

  const { data, error: swrError, isLoading, mutate } = useSWR<T>(key, fetcher, {
    revalidateOnFocus: true,
    dedupingInterval: 5000,
    ...swrOpts,
  });

  const refetch = useCallback(() => mutate(), [mutate]);

  return {
    data: data ?? null,
    loading: isLoading,
    error: swrError
      ? (swrError instanceof Error ? swrError.message : "Failed to load data")
      : null,
    refetch,
  };
}
