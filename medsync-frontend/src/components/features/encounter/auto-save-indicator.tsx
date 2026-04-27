"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";

interface AutoSaveIndicatorProps {
  isSaving: boolean;
  lastSavedAt: string | null;
  error?: Error | null;
}

export function AutoSaveIndicator({ isSaving, lastSavedAt, error }: AutoSaveIndicatorProps) {
  const [showSaveNotification, setShowSaveNotification] = useState(false);
  const prevLastSavedAtRef = useRef<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Callback to show notification - can be safely called from effect
  const showNotification = useCallback(() => {
    setShowSaveNotification(true);
    // Clear any existing timer
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      setShowSaveNotification(false);
    }, 3000);
  }, []);

  // Track previous value and trigger notification when save completes
  useEffect(() => {
    // Check if lastSavedAt changed and a save just completed
    const savedAtChanged = lastSavedAt && lastSavedAt !== prevLastSavedAtRef.current;
    const saveJustCompleted = savedAtChanged && !isSaving;
    
    if (saveJustCompleted) {
      prevLastSavedAtRef.current = lastSavedAt;
      // Schedule notification for next tick to avoid synchronous setState
      const id = requestAnimationFrame(() => showNotification());
      return () => cancelAnimationFrame(id);
    }
  }, [lastSavedAt, isSaving, showNotification]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  if (error) {
    return (
      <div className="fixed bottom-4 right-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 max-w-sm">
        <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
          <span className="text-white text-xs">!</span>
        </div>
        <div className="flex flex-col">
          <p className="text-sm font-medium text-red-900">Save failed</p>
          <p className="text-xs text-red-700">{error.message}</p>
        </div>
      </div>
    );
  }

  if (showSaveNotification && lastSavedAt) {
    return (
      <div className="fixed bottom-4 right-4 bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 animate-in fade-in-0 slide-in-from-bottom-4 duration-300">
        <Check className="w-5 h-5 text-green-600" />
        <p className="text-sm font-medium text-green-900">Saved at {lastSavedAt}</p>
      </div>
    );
  }

  if (isSaving) {
    return (
      <div className="fixed bottom-4 right-4 bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-sm text-blue-900">Saving...</p>
      </div>
    );
  }

  return null;
}
