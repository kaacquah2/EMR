"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useAuth } from "@/lib/auth-context";
import type { AuthTokens } from "@/lib/types";
import { API_BASE } from "@/lib/api-base";

type Step = "credentials" | "mfa";
type MfaMode = "totp" | "backup";
type MfaChannel = "email" | "authenticator";

export default function LoginPage() {
  const { login } = useAuth();
  const [step, setStep] = useState<Step>("credentials");
  const [mfaMode, setMfaMode] = useState<MfaMode>("totp");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState(["", "", "", "", "", ""]);
  const [backupCode, setBackupCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaChannel, setMfaChannel] = useState<MfaChannel | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(30);

  const handleCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let res: Response;
      try {
        res = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      } catch {
        setError("Sign-in is temporarily unavailable. Check your connection and try again.");
        return;
      }
      let data: {
        message?: string;
        mfa_required?: boolean;
        mfa_token?: string;
        mfa_channel?: MfaChannel;
        access_token?: string;
      };
      try {
        data = await res.json();
      } catch {
        setError(
          `The server did not return JSON (HTTP ${res.status}). ` +
            `Confirm NEXT_PUBLIC_API_URL in your deploy points to the Django API base ending in /api/v1, then redeploy the frontend.`,
        );
        return;
      }
      if (res.status === 503 || res.status === 502) {
        setError(data.message || "We could not send your sign-in code. Try again later or contact support.");
        return;
      }
      if (!res.ok) {
        setError(
          data.message ||
            (res.status === 401 ? "Invalid credentials" : `Sign-in failed (HTTP ${res.status})`),
        );
        return;
      }
      if (data.mfa_required) {
        setMfaToken(data.mfa_token ?? null);
        const ch = data.mfa_channel;
        setMfaChannel(ch === "email" || ch === "authenticator" ? ch : "authenticator");
        setStep("mfa");
        setTimeRemaining(30);
      } else if (data.access_token) {
        login(data as AuthTokens, { rememberMe });
        const role = (data as AuthTokens).user_profile?.role;
        window.location.href = role === "super_admin" ? "/superadmin" : "/dashboard";
      }
    } catch {
      setError("Login failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (step !== "mfa" || mfaChannel !== "authenticator") return;

    const interval = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) return 30;
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [step, mfaChannel]);

  const handleMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const body: Record<string, string> = { mfa_token: mfaToken || "" };
    if (mfaMode === "backup") {
      body.backup_code = backupCode;
    } else {
      body.code = mfaCode.join("");
    }
    try {
      const res = await fetch(`${API_BASE}/auth/mfa-verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.message || "Invalid code";
        if (
          mfaMode === "totp" &&
          mfaChannel === "authenticator" &&
          msg.toLowerCase().includes("invalid")
        ) {
          setError(`${msg}. Tip: Make sure your device's date and time are correct.`);
        } else {
          setError(msg);
        }
        throw new Error();
      }
      login(data as AuthTokens, { rememberMe });
      document.cookie = "medsync_session=1; path=/; max-age=28800";
      const role = (data as AuthTokens).user_profile?.role;
      window.location.href = role === "super_admin" ? "/superadmin" : "/dashboard";
    } catch {
      //
    } finally {
      setLoading(false);
    }
  };

  const handleMfaInput = (i: number, v: string) => {
    if (v.length > 1) {
      const digits = v.replace(/\D/g, "").slice(0, 6).split("");
      const next = [...mfaCode];
      digits.forEach((d, j) => {
        if (i + j < 6) next[i + j] = d;
      });
      setMfaCode(next);
      const lastIdx = Math.min(i + digits.length, 5);
      const el = document.getElementById(`mfa-${lastIdx}`);
      if (el) (el as HTMLInputElement).focus();
      return;
    }
    const next = [...mfaCode];
    next[i] = v.replace(/\D/g, "").slice(-1);
    setMfaCode(next);
    if (v && i < 5) {
      const el = document.getElementById(`mfa-${i + 1}`);
      if (el) (el as HTMLInputElement).focus();
    }
  };

  return (
    <AuthLayout title="MedSync" subtitle="One Record. Every Hospital.">
      {step === "credentials" ? (
        <form key="credentials" onSubmit={handleCredentials} className="space-y-4">
          <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Sign in to MedSync</h2>
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@hospital.gov.gh"
            required
            autoFocus
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
          <label className="flex items-center gap-2 text-sm text-[#475569]">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-[#CBD5E1] text-[#0B8A96] focus:ring-[#0B8A96]"
            />
            Remember me (keep signed in after closing tab)
          </label>
          <Link href="/forgot-password" className="block text-sm text-[#0B8A96] hover:underline">
            Forgot password?
          </Link>
          {error && <p className="text-sm text-[#DC2626]">{error}</p>}
          <Button type="submit" fullWidth disabled={loading}>
            {loading ? "Signing in..." : "Continue"}
          </Button>
        </form>
      ) : (
        <form key="mfa" onSubmit={handleMfa} className="space-y-4">
          <h2 className="font-sora text-lg font-semibold text-[#0F172A]">
            {mfaMode === "backup"
              ? "Enter backup code"
              : mfaChannel === "email"
                ? "Enter the 6-digit code from your email"
                : "Enter your 6-digit code"}
          </h2>
          {mfaMode === "totp" ? (
            <>
              <p className="text-sm text-[#64748B]">
                {mfaChannel === "email"
                  ? "We sent a one-time code to your email. Enter it below."
                  : "Open your authenticator app to get the code."}
              </p>
              <div className="space-y-3">
                <div className="flex justify-center gap-2">
                  {mfaCode.map((c, i) => (
                    <input
                      key={i}
                      id={`mfa-${i}`}
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={c}
                      onChange={(e) => handleMfaInput(i, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Backspace" && !c && i > 0) {
                          const el = document.getElementById(`mfa-${i - 1}`);
                          if (el) (el as HTMLInputElement).focus();
                        }
                      }}
                      className="h-12 w-10 rounded-lg border-2 border-[#CBD5E1] text-center font-mono text-lg focus:border-[#0B8A96] focus:outline-none focus:ring-2 focus:ring-[#0B8A96]/20"
                    />
                  ))}
                </div>
                {mfaChannel === "authenticator" ? (
                  <>
                    <div className="flex items-center justify-between rounded-lg bg-[#F1F5F9] p-3">
                      <span className="text-xs text-[#64748B]">Code expires in</span>
                      <span
                        className={`font-mono text-sm font-semibold ${timeRemaining <= 10 ? "text-[#DC2626]" : "text-[#0B8A96]"}`}
                      >
                        {timeRemaining}s
                      </span>
                    </div>
                    {timeRemaining <= 5 && (
                      <p className="text-xs text-[#DC2626]">
                        New code coming soon. Your entry will refresh automatically.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-center text-xs text-[#64748B]">This code expires in 5 minutes.</p>
                )}
              </div>
              <div className="space-y-2 rounded-lg bg-[#EFF6F9] p-3">
                <p className="text-xs font-semibold text-[#0B8A96]">Having issues?</p>
                <ul className="space-y-1 text-xs text-[#64748B]">
                  {mfaChannel === "email" ? (
                    <>
                      <li>Check your inbox for the latest message from MedSync.</li>
                      <li>If you do not see it, check spam or junk.</li>
                      <li>Use a backup code if the email code does not work.</li>
                    </>
                  ) : (
                    <>
                      <li>Check your device&apos;s date/time settings</li>
                      <li>Wait 30 seconds and try the next code</li>
                      <li>Use a backup code if the authenticator code does not work</li>
                    </>
                  )}
                </ul>
              </div>
              <button
                type="button"
                onClick={() => {
                  setMfaMode("backup");
                  setError("");
                  setBackupCode("");
                }}
                className="block w-full text-center text-sm text-[#0B8A96] hover:underline"
              >
                Use backup code
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-[#64748B]">Enter one of your single-use backup codes.</p>
              <input
                type="text"
                value={backupCode}
                onChange={(e) => setBackupCode(e.target.value)}
                placeholder="xxxxxxxx"
                className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3 font-mono"
                required
              />
              <button
                type="button"
                onClick={() => {
                  setMfaMode("totp");
                  setError("");
                  setBackupCode("");
                }}
                className="block w-full text-center text-sm text-[#0B8A96] hover:underline"
              >
                Use authenticator app instead
              </button>
            </>
          )}
          {error && <p className="text-sm text-[#DC2626]">{error}</p>}
          <Button
            type="submit"
            fullWidth
            disabled={
              loading ||
              (mfaMode === "totp" && mfaCode.join("").length !== 6) ||
              (mfaMode === "backup" && !backupCode.trim())
            }
          >
            {loading ? "Verifying..." : "Verify"}
          </Button>
          <button
            type="button"
            onClick={() => {
              setStep("credentials");
              setMfaMode("totp");
              setMfaChannel(null);
              setMfaCode(["", "", "", "", "", ""]);
              setBackupCode("");
              setError("");
            }}
            className="w-full text-sm text-[#64748B] hover:text-[#0F172A]"
          >
            Back to sign in
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
