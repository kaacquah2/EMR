"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/Checkbox";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useAuth } from "@/lib/auth-context";
import { usePasskey } from "@/hooks/use-passkey";
import type { AuthTokens } from "@/lib/types";
import { API_BASE } from "@/lib/api-base";
import { validateDevicePolicy, cacheDevicePolicyCheck, getCachedDevicePolicy } from "@/lib/device-policy";
import type { DevicePolicy } from "@/lib/device-policy";

type Step = "credentials" | "passkey" | "password" | "mfa";
type MfaMode = "totp" | "backup";
type MfaChannel = "email" | "authenticator";

// UX-09: Context-aware save button labels per step
const STEP_LABELS: Record<Step, string> = {
  credentials: "Sign in",
  passkey: "Sign in",
  password: "Sign in",
  mfa: "Verify code",
};

export default function LoginPage() {
  const { login } = useAuth();
  const passkey = usePasskey();
  const [step, setStep] = useState<Step>("credentials");
  const [mfaMode, setMfaMode] = useState<MfaMode>("totp");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState(["", "", "", "", "", ""]);
  const [backupCode, setBackupCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaChannel, setMfaChannel] = useState<MfaChannel | null>(null);
  // UX-04: errors use role="alert"
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(30);
  const [devicePolicy, setDevicePolicy] = useState<DevicePolicy | null>(null);
  const [userHasPasskey, setUserHasPasskey] = useState(false);
  const [checkingPasskey, setCheckingPasskey] = useState(false);
  // UX-02: Resend code state
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendLoading, setResendLoading] = useState(false);

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
        // UX-02: start resend cooldown for email OTP
        if (ch === "email") setResendCooldown(60);
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

  // UX-02: Resend OTP handler
  const handleResend = async () => {
    if (resendCooldown > 0 || !mfaToken) return;
    setResendLoading(true);
    try {
      await fetch(`${API_BASE}/auth/mfa-resend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mfa_token: mfaToken }),
      });
      setResendCooldown(60);
      setMfaCode(["", "", "", "", "", ""]);
      setError("");
    } catch {
      setError("Could not resend code. Please try again.");
    } finally {
      setResendLoading(false);
    }
  };

  // UX-02: Resend cooldown countdown
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setInterval(() => setResendCooldown((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(t);
  }, [resendCooldown]);

  useEffect(() => {
    const cached = getCachedDevicePolicy();
    if (cached) {
      setDevicePolicy(cached);
    } else {
      const policy = validateDevicePolicy();
      setDevicePolicy(policy);
      cacheDevicePolicyCheck(policy);
    }
  }, []);

  useEffect(() => {
    if (!email || !email.includes("@")) {
      setUserHasPasskey(false);
      return;
    }
    setCheckingPasskey(true);
    const checkPasskey = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/passkey/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const data = await res.json();
        setUserHasPasskey(data.has_passkeys === true);
      } catch {
        setUserHasPasskey(false);
      } finally {
        setCheckingPasskey(false);
      }
    };
    const timer = setTimeout(checkPasskey, 300);
    return () => clearTimeout(timer);
  }, [email]);

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
        if (mfaMode === "totp" && mfaChannel === "authenticator" && msg.toLowerCase().includes("invalid")) {
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

  const handlePasskeyLogin = async () => {
    if (!email) { setError("Please enter your email first"); return; }
    setError("");
    setLoading(true);
    try {
      const result = await passkey.authenticate(email);
      login(result as AuthTokens, { rememberMe });
      const role = (result as AuthTokens).role;
      window.location.href = role === "super_admin" ? "/superadmin" : "/dashboard";
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Passkey authentication failed. Try password instead.";
      setError(message);
      setStep("password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="MedSync" subtitle="One Record. Every Hospital.">
      {/* UX-28: Apply login-form-enter animation on step change */}
      {step === "credentials" ? (
        <form key="credentials" onSubmit={handleCredentials} className="login-form-enter space-y-4">
          <h2 className="font-sora text-lg font-semibold text-[var(--gray-900)]">Sign in to MedSync</h2>

          {devicePolicy && !devicePolicy.isSupported && devicePolicy.warning && (
            <div className="rounded-lg border border-[#FCD34D] bg-[#FEF3C7] p-3 text-sm text-[#92400E]" role="alert">
              <p className="font-medium">{devicePolicy.warning}</p>
              <p className="mt-1 text-xs">Supported: Windows (Hello) · macOS (Touch ID/Face ID)</p>
            </div>
          )}

          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@hospital.gov.gh"
            data-testid="login-email"
            className="bg-white text-gray-900 dark:bg-white dark:text-gray-900 autofill-override"
            required
            autoFocus
          />

          {passkey.isSupported && email && passkey.isPlatformAvailable && userHasPasskey && !checkingPasskey && (
            <div className="border-t pt-4">
              <p className="mb-3 text-xs text-[var(--gray-500)]">Sign in with your saved passkey</p>
              <Button type="button" fullWidth variant="outline" onClick={handlePasskeyLogin} disabled={loading} data-testid="login-passkey">
                {loading ? "Signing in…" : "👆 Sign in with passkey (fingerprint/face ID)"}
              </Button>
              <p className="mt-2 text-center text-xs text-[var(--gray-500)]">No code needed — just your fingerprint or face</p>
              <hr className="my-4 border-[var(--gray-300)]" />
              <p className="mb-3 text-xs text-[var(--gray-500)]">Or continue with password</p>
            </div>
          )}

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            data-testid="login-password"
            className="bg-white text-gray-900 dark:bg-white dark:text-gray-900 autofill-override"
            required
          />

          <Checkbox
            label="Remember me (keep signed in after closing tab)"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />

          <Link href="/forgot-password" className="block text-sm text-[var(--teal-500)] hover:underline">
            Forgot password?
          </Link>

          {/* UX-04: role="alert" on error */}
          {error && <p className="text-sm text-[var(--red-600)]" role="alert" aria-live="polite">{error}</p>}

          {/* UX-01: "Sign in" instead of "Continue" */}
          <Button
            type="submit"
            fullWidth
            disabled={loading || !email || !password}
            data-testid="login-submit"
          >
            {loading ? "Signing in…" : STEP_LABELS[step]}
          </Button>
        </form>
      ) : (
        <form key="mfa" onSubmit={handleMfa} className="login-form-enter space-y-4">
          <h2 className="font-sora text-lg font-semibold text-[var(--gray-900)]">
            {mfaMode === "backup"
              ? "Enter backup code"
              : mfaChannel === "email"
                ? "Enter the 6-digit code from your email"
                : "Enter your 6-digit code"}
          </h2>

          {mfaMode === "totp" ? (
            <>
              <p className="text-sm text-[var(--gray-500)]">
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
                      data-testid={`mfa-code-${i}`}
                      className="h-12 w-10 rounded-lg border-2 border-[var(--gray-300)] bg-white text-slate-900 dark:bg-white dark:text-slate-900 text-center font-mono text-lg focus:border-[var(--teal-500)] focus:outline-none focus:ring-2 focus:ring-[rgba(11,138,150,0.2)] autofill-override"
                    />
                  ))}
                </div>

                {mfaChannel === "authenticator" ? (
                  <>
                    <div className="flex items-center justify-between rounded-lg bg-[var(--gray-100)] p-3">
                      <span className="text-xs text-[var(--gray-500)]">Code expires in</span>
                      <span className={`font-mono text-sm font-semibold ${timeRemaining <= 10 ? "text-[var(--red-600)]" : "text-[var(--teal-500)]"}`}>
                        {timeRemaining}s
                      </span>
                    </div>
                    {timeRemaining <= 5 && (
                      <p className="text-xs text-[var(--red-600)]">New code coming soon. Your entry will refresh automatically.</p>
                    )}
                  </>
                ) : (
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-[var(--gray-500)]">This code expires in 5 minutes.</p>
                    {/* UX-02: Resend code for email OTP */}
                    <button
                      type="button"
                      onClick={handleResend}
                      disabled={resendCooldown > 0 || resendLoading}
                      className="text-xs font-semibold text-[var(--teal-500)] hover:underline disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {resendLoading ? "Sending…" : resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend code"}
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-2 rounded-lg bg-[#EFF6F9] p-3">
                <p className="text-xs font-semibold text-[var(--teal-500)]">Having issues?</p>
                <ul className="space-y-1 text-xs text-[var(--gray-500)]">
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
                onClick={() => { setMfaMode("backup"); setError(""); setBackupCode(""); }}
                className="block w-full text-center text-sm text-[var(--teal-500)] hover:underline"
              >
                Use backup code
              </button>
            </>
          ) : (
            <>
              <Input
                label="Backup Code"
                value={backupCode}
                onChange={(e) => setBackupCode(e.target.value)}
                placeholder="xxxxxxxx"
                data-testid="mfa-backup-code"
                className="font-mono"
                required
              />
              <button
                type="button"
                onClick={() => { setMfaMode("totp"); setError(""); setBackupCode(""); }}
                className="block w-full text-center text-sm text-[var(--teal-500)] hover:underline"
              >
                Use authenticator app instead
              </button>
            </>
          )}

          {/* UX-04: role="alert" on error */}
          {error && <p className="text-sm text-[var(--red-600)]" role="alert" aria-live="polite">{error}</p>}

          {/* UX-01: "Verify code" label */}
          <Button
            type="submit"
            fullWidth
            disabled={
              loading ||
              (mfaMode === "totp" && mfaCode.join("").length !== 6) ||
              (mfaMode === "backup" && !backupCode.trim())
            }
            data-testid="mfa-submit"
          >
            {loading ? "Verifying…" : "Verify code"}
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
            className="w-full text-sm text-[var(--gray-500)] hover:text-[var(--gray-900)]"
          >
            ← Back to sign in
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
