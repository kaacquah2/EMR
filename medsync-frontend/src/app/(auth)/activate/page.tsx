"use client";

import React, { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { validatePassword, PASSWORD_REQUIREMENTS } from "@/lib/password-policy";
import { API_BASE } from "@/lib/api-base";

function ActivateForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showBackupCodes, setShowBackupCodes] = useState<string[] | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    const pwCheck = validatePassword(password);
    if (!pwCheck.valid) {
      setError(pwCheck.message || "Invalid password");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          totp_confirmation: mfaCode,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Activation failed");
      if (data.backup_codes?.length) {
        setShowBackupCodes(data.backup_codes);
        login(data);
      } else {
        login(data);
        document.cookie = "medsync_session=1; path=/; max-age=28800";
        window.location.href = "/dashboard";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <>
        <div className="rounded-xl border border-[#D97706]/30 bg-[#FEF3C7]/60 p-4 text-[#92400E]">
          <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Invalid or missing invitation link</h2>
          <p className="mt-1 text-sm">Please use the link from your invitation email.</p>
        </div>
      </>
    );
  }

  if (showBackupCodes) {
    return (
      <>
        <h2 className="font-sora text-xl font-bold text-[#0C1F3D]">Save your backup codes</h2>
        <p className="mt-1 text-sm text-[#64748B]">
          Store these codes securely. Each can be used once if you lose access to your authenticator.
        </p>
        <div className="mt-4 rounded-xl border border-[#0B8A96]/25 bg-[#F0FDFA]/70 p-4 font-mono text-sm text-[#0F172A]">
          {showBackupCodes.map((c, i) => (
            <p key={i} className="py-0.5">{c}</p>
          ))}
        </div>
        <Button
          className="mt-6 w-full"
          onClick={() => {
            document.cookie = "medsync_session=1; path=/; max-age=28800";
            window.location.href = "/dashboard";
          }}
        >
          Continue to dashboard
        </Button>
      </>
    );
  }

  return (
    <>
      <div className="mb-4 rounded-lg border border-[#0B8A96]/20 bg-[#F0FDFA]/50 p-3">
        <ul className="list-inside list-disc text-xs text-[#0F172A]">
          {PASSWORD_REQUIREMENTS.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Min 12 characters"
          required
          minLength={12}
        />
        <Input
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Repeat password"
          required
        />
        <Input
          label="Authenticator code"
          type="text"
          value={mfaCode}
          onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          placeholder="6-digit code from your app"
          required
          maxLength={6}
        />
        {error && <p className="text-sm text-[#DC2626]">{error}</p>}
        <Button type="submit" fullWidth disabled={loading}>
          {loading ? "Activating..." : "Activate account"}
        </Button>
      </form>
    </>
  );
}

export default function ActivatePage() {
  return (
    <AuthLayout title="Set up your account" subtitle="Create your password and enable two-factor authentication.">
      <Suspense fallback={<p className="text-[#64748B]">Loading...</p>}>
        <ActivateForm />
      </Suspense>
    </AuthLayout>
  );
}
