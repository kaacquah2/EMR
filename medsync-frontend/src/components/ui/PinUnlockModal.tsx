"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api-base";

export function PinUnlockModal() {
  const { isLocked, setIsLocked, getRefreshToken, logout, setTokens } = useAuth();
  const [pin, setPin] = useState<string[]>(["", "", "", ""]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Submit automatically when all 4 digits are entered
  const isComplete = pin.every((digit) => digit !== "");

  const submitPin = useCallback(async () => {
    if (!isComplete || loading) return;
    setLoading(true);
    setError("");

    try {
      const refreshToken = getRefreshToken();
      const res = await fetch(`${API_BASE}/auth/session-unlock`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          pin: pin.join(""),
          refresh_token: refreshToken,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.message || "Invalid PIN. Please try again.");
        setPin(["", "", "", ""]);
        inputRefs.current[0]?.focus();
        return;
      }

      // Session unlocked: update tokens locally
      const { access_token, refresh_token } = data;
      setTokens({ access_token, refresh_token });
      setIsLocked(false);
    } catch {
      setError("An error occurred. Please verify your connection.");
    } finally {
      setLoading(false);
    }
  }, [isComplete, loading, pin, getRefreshToken, setIsLocked, setTokens]);

  // Auto-focus first input on mount / lock
  useEffect(() => {
    if (isLocked) {
      setError("");
      setPin(["", "", "", ""]);
      setTimeout(() => {
        inputRefs.current[0]?.focus();
      }, 100);
    }
  }, [isLocked]);

  // Auto trigger submit when all inputs filled
  useEffect(() => {
    if (!isLocked) return;
    if (isComplete) {
      submitPin();
    }
  }, [isComplete, submitPin, isLocked]);

  if (!isLocked) return null;

  const handleInput = (index: number, val: string) => {
    const cleaned = val.replace(/\D/g, "").slice(-1);
    const nextPin = [...pin];
    nextPin[index] = cleaned;
    setPin(nextPin);
    setError("");

    if (cleaned && index < 3) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (!pin[index] && index > 0) {
        const nextPin = [...pin];
        nextPin[index - 1] = "";
        setPin(nextPin);
        inputRefs.current[index - 1]?.focus();
      } else {
        const nextPin = [...pin];
        nextPin[index] = "";
        setPin(nextPin);
      }
      setError("");
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 4);
    if (pasted.length === 4) {
      const nextPin = pasted.split("");
      setPin(nextPin);
      inputRefs.current[3]?.focus();
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/80 backdrop-blur-md">
      <div className="w-full max-w-md rounded-2xl border border-slate-100 bg-white p-8 shadow-2xl dark:border-slate-800 dark:bg-slate-950 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-500">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="h-7 w-7"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
            />
          </svg>
        </div>

        <h2 className="font-sora text-xl font-bold text-slate-900 dark:text-white">
          Workstation Locked
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Your session was locked due to 15 minutes of inactivity. Enter your 4-digit PIN to resume.
        </p>

        <div className="mt-6 flex justify-center gap-3">
          {pin.map((digit, index) => (
            <input
              key={index}
              ref={(el) => { inputRefs.current[index] = el; }}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={1}
              value={digit}
              onChange={(e) => handleInput(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              onPaste={index === 0 ? handlePaste : undefined}
              disabled={loading}
              className="h-14 w-12 rounded-xl border-2 border-slate-200 bg-white text-center text-2xl font-bold text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            />
          ))}
        </div>

        {error && (
          <p
            className="mt-4 text-sm font-semibold text-red-600 dark:text-red-400"
            role="alert"
            aria-live="polite"
          >
            {error}
          </p>
        )}

        <div className="mt-8 flex flex-col gap-3">
          <Button
            variant="secondary"
            onClick={logout}
            className="w-full text-sm font-semibold"
          >
            Switch User / Log Out
          </Button>
        </div>
      </div>
    </div>
  );
}
