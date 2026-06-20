"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";

export function PinSetupModal() {
  const { pinSetupRequired, setPinSetupRequired } = useAuth();
  const api = useApi();
  const [step, setStep] = useState<"enter" | "confirm">("enter");
  const [pin, setPin] = useState<string[]>(["", "", "", ""]);
  const [confirmPin, setConfirmPin] = useState<string[]>(["", "", "", ""]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const pinRefs = useRef<(HTMLInputElement | null)[]>([]);
  const confirmRefs = useRef<(HTMLInputElement | null)[]>([]);

  const isPinComplete = pin.every((d) => d !== "");
  const isConfirmComplete = confirmPin.every((d) => d !== "");

  const handleNext = useCallback(() => {
    if (isPinComplete) {
      setStep("confirm");
      setTimeout(() => {
        confirmRefs.current[0]?.focus();
      }, 50);
    }
  }, [isPinComplete]);

  const handleSubmit = useCallback(async () => {
    if (!isPinComplete || !isConfirmComplete || loading) return;

    const pinStr = pin.join("");
    const confirmStr = confirmPin.join("");

    if (pinStr !== confirmStr) {
      setError("PINs do not match. Please start over.");
      setPin(["", "", "", ""]);
      setConfirmPin(["", "", "", ""]);
      setStep("enter");
      setTimeout(() => {
        pinRefs.current[0]?.focus();
      }, 50);
      return;
    }

    setLoading(true);
    setError("");

    try {
      await api.post("/auth/set-device-pin", { pin: pinStr });
      setPinSetupRequired(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to set PIN. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [isPinComplete, isConfirmComplete, loading, pin, confirmPin, api, setPinSetupRequired]);

  useEffect(() => {
    if (pinSetupRequired) {
      setStep("enter");
      setPin(["", "", "", ""]);
      setConfirmPin(["", "", "", ""]);
      setError("");
      setTimeout(() => {
        pinRefs.current[0]?.focus();
      }, 100);
    }
  }, [pinSetupRequired]);

  // Auto transition to confirm step
  useEffect(() => {
    if (!pinSetupRequired) return;
    if (step === "enter" && isPinComplete) {
      handleNext();
    }
  }, [pin, step, isPinComplete, handleNext, pinSetupRequired]);

  // Auto trigger submit on confirm complete
  useEffect(() => {
    if (!pinSetupRequired) return;
    if (step === "confirm" && isConfirmComplete) {
      handleSubmit();
    }
  }, [confirmPin, step, isConfirmComplete, handleSubmit, pinSetupRequired]);

  if (!pinSetupRequired) return null;

  const handleInput = (index: number, val: string, isConfirm: boolean) => {
    const cleaned = val.replace(/\D/g, "").slice(-1);
    if (isConfirm) {
      const nextConfirm = [...confirmPin];
      nextConfirm[index] = cleaned;
      setConfirmPin(nextConfirm);
      setError("");
      if (cleaned && index < 3) {
        confirmRefs.current[index + 1]?.focus();
      }
    } else {
      const nextPin = [...pin];
      nextPin[index] = cleaned;
      setPin(nextPin);
      setError("");
      if (cleaned && index < 3) {
        pinRefs.current[index + 1]?.focus();
      }
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>, isConfirm: boolean) => {
    if (e.key === "Backspace") {
      if (isConfirm) {
        const nextConfirm = [...confirmPin];
        if (!confirmPin[index] && index > 0) {
          nextConfirm[index - 1] = "";
          confirmRefs.current[index - 1]?.focus();
        } else {
          nextConfirm[index] = "";
        }
        setConfirmPin(nextConfirm);
      } else {
        const nextPin = [...pin];
        if (!pin[index] && index > 0) {
          nextPin[index - 1] = "";
          pinRefs.current[index - 1]?.focus();
        } else {
          nextPin[index] = "";
        }
        setPin(nextPin);
      }
      setError("");
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-100 bg-white p-8 shadow-2xl dark:border-slate-800 dark:bg-slate-950 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-teal-50 text-teal-600 dark:bg-teal-950/30 dark:text-teal-500">
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
              d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
            />
          </svg>
        </div>

        <h2 className="font-sora text-xl font-bold text-slate-900 dark:text-white">
          Workstation PIN Setup
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          {step === "enter"
            ? "Create a 4-digit PIN for quick re-authentication on this workstation."
            : "Confirm your 4-digit PIN."}
        </p>

        <div className="mt-6 flex justify-center gap-3">
          {step === "enter"
            ? pin.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { pinRefs.current[index] = el; }}
                  type="password"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleInput(index, e.target.value, false)}
                  onKeyDown={(e) => handleKeyDown(index, e, false)}
                  disabled={loading}
                  className="h-14 w-12 rounded-xl border-2 border-slate-200 bg-white text-center text-2xl font-bold text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                />
              ))
            : confirmPin.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { confirmRefs.current[index] = el; }}
                  type="password"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleInput(index, e.target.value, true)}
                  onKeyDown={(e) => handleKeyDown(index, e, true)}
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

        <div className="mt-8 flex justify-between gap-4">
          {step === "confirm" && (
            <Button
              variant="secondary"
              onClick={() => {
                setStep("enter");
                setConfirmPin(["", "", "", ""]);
                setError("");
                setTimeout(() => pinRefs.current[0]?.focus(), 50);
              }}
              disabled={loading}
              className="w-1/2"
            >
              Back
            </Button>
          )}
          <Button
            onClick={step === "enter" ? handleNext : handleSubmit}
            disabled={
              loading ||
              (step === "enter" && !isPinComplete) ||
              (step === "confirm" && !isConfirmComplete)
            }
            className={step === "enter" ? "w-full" : "w-1/2"}
          >
            {loading ? "Saving..." : step === "enter" ? "Next" : "Save PIN"}
          </Button>
        </div>
      </div>
    </div>
  );
}
