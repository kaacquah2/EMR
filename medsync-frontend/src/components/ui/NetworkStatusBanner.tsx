"use client";

import React, { useEffect, useState } from "react";
import { AlertCircle, WifiOff, RefreshCcw } from "lucide-react";

export function NetworkStatusBanner() {
  const [isOffline, setIsOffline] = useState(
    () => typeof navigator !== "undefined" && !navigator.onLine
  );
  const [hasApiError, setHasApiError] = useState(false);

  useEffect(() => {
    const handleOffline = () => setIsOffline(true);
    const handleOnline = () => {
      setIsOffline(false);
      setHasApiError(false);
    };

    // Custom event dispatched from api-client when a request fails due to network/timeout
    const handleApiError = () => setHasApiError(true);

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    window.addEventListener("medsync:apierror", handleApiError);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("medsync:apierror", handleApiError);
    };
  }, []);

  const handleRetry = () => {
    window.location.reload();
  };

  if (!isOffline && !hasApiError) return null;

  return (
    <div className="fixed top-0 left-0 z-50 w-full bg-red-600 px-4 py-3 text-white shadow-md transition-all">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          {isOffline ? <WifiOff className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
          <div>
            <p className="font-semibold text-sm">
              {isOffline ? "You are currently offline" : "Connection to server lost"}
            </p>
            <p className="text-xs text-red-100 hidden sm:block">
              {isOffline
                ? "Please check your internet connection. Some features may be unavailable."
                : "We're having trouble connecting to the MedSync servers."}
            </p>
          </div>
        </div>
        <button
          onClick={handleRetry}
          className="flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-red-600"
        >
          <RefreshCcw className="h-4 w-4" />
          Retry
        </button>
      </div>
    </div>
  );
}
