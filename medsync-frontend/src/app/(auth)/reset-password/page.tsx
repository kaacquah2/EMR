"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { validatePassword, PASSWORD_REQUIREMENTS } from "@/lib/password-policy";
import { API_BASE } from "@/lib/api-base";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    const pwCheck = validatePassword(password);
    if (!pwCheck.valid) {
      setError(pwCheck.message ?? "Invalid password");
      return;
    }
    if (!token) {
      setError("Reset link is invalid or missing. Request a new link from the forgot password page.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        // Avoid surfacing internal error details; display generic message
        throw new Error("Unable to reset password. Please try again.");
      }
      login(data);
      document.cookie = "medsync_session=1; path=/; max-age=28800";
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <>
        <div className="rounded-xl border border-[#D97706]/30 bg-[#FEF3C7]/60 p-4 text-[#92400E]">
          <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Invalid reset link</h2>
          <p className="mt-1 text-sm">
            This page requires a valid token. Request a new password reset link.
          </p>
        </div>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link href="/forgot-password" className="text-sm font-medium text-[#0B8A96] hover:underline">
            Forgot password
          </Link>
          <Link href="/login" className="text-sm text-[#64748B] hover:text-[#0F172A]">
            Back to sign in
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <h2 className="font-sora text-xl font-bold text-[#0C1F3D]">Set new password</h2>
      <p className="mt-1 text-sm text-[#64748B]">
        Enter your new password below. It must meet the requirements listed.
      </p>
      <div className="mt-3 rounded-lg border border-[#0B8A96]/20 bg-[#F0FDFA]/50 p-3">
        <ul className="list-inside list-disc text-xs text-[#0F172A]">
          {PASSWORD_REQUIREMENTS.map((req) => (
            <li key={req}>{req}</li>
          ))}
        </ul>
      </div>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <Input
          label="New password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          required
          autoComplete="new-password"
        />
        <Input
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="••••••••"
          required
          autoComplete="new-password"
        />
        {error && <p className="text-sm text-[#DC2626]">{error}</p>}
        <Button type="submit" fullWidth disabled={loading}>
          {loading ? "Resetting..." : "Reset password"}
        </Button>
        <Link href="/login" className="block text-center text-sm text-[#64748B] hover:text-[#0F172A]">
          Back to sign in
        </Link>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthLayout title="Reset password" subtitle="Set a new password for your account.">
      <Suspense fallback={<p className="text-[#64748B]">Loading...</p>}>
        <ResetPasswordForm />
      </Suspense>
    </AuthLayout>
  );
}
