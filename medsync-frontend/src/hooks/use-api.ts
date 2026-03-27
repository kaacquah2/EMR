"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import { createApiClient } from "@/lib/api-client";

export function useApi() {
  const { getAccessToken, refreshTokens, updateActivity, getViewAsHeader } = useAuth();
  return useMemo(
    () => createApiClient(getAccessToken, refreshTokens, updateActivity, getViewAsHeader),
    [getAccessToken, refreshTokens, updateActivity, getViewAsHeader]
  );
}
