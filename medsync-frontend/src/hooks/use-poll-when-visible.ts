"use client";

import { useEffect, useRef } from "react";

/**
 * Run a callback on an interval only when the document is visible (tab focused).
 * Use for worklist and lab-result polling so doctors see updates after handoffs.
 *
 * @param callback - Function to run on each tick (e.g. refetch)
 * @param intervalMs - Interval in milliseconds (e.g. 45000 for 45s)
 * @param enabled - When false, polling is not started
 */
export function usePollWhenVisible(
  callback: () => void,
  intervalMs: number,
  enabled: boolean
): void {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const tick = () => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        callbackRef.current();
      }
    };

    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}
