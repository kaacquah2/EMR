"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { API_BASE } from "@/lib/api-base";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // UX-03: auto-redirect countdown
  const [countdown, setCountdown] = useState(10);

  useEffect(() => {
    if (!sent) return;
    if (countdown <= 0) {
      window.location.href = "/login";
      return;
    }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [sent, countdown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        throw new Error("Unable to send reset link. Please try again.");
      }
      setSent(true);
    } catch {
      setError("Unable to send reset link. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Forgot password" subtitle="Enter your email and we'll send you a reset link.">
      {sent ? (
        <div className="rounded-xl border border-[#059669]/30 bg-[#D1FAE5]/80 p-5 text-[#047857]">
          <p className="font-semibold">Check your email</p>
          <p className="mt-1 text-sm">
            If an account exists for {email}, you&apos;ll receive a password reset link shortly.
          </p>
          {/* UX-03: countdown auto-redirect */}
          <p className="mt-3 text-xs text-[#047857]/70">
            Returning to sign in in {countdown}s…
          </p>
          <Link
            href="/login"
            className="mt-4 inline-flex items-center text-sm font-medium text-[var(--teal-500)] hover:underline"
          >
            ← Back to sign in now
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@hospital.gov.gh"
            required
            autoFocus
          />
          {error && <p className="text-sm text-[var(--red-600)]" role="alert">{error}</p>}
          <Button type="submit" fullWidth disabled={loading}>
            {loading ? "Sending…" : "Send reset link"}
          </Button>
          <Link
            href="/login"
            className="block text-center text-sm text-[var(--gray-500)] hover:text-[var(--gray-900)]"
          >
            ← Back to sign in
          </Link>
        </form>
      )}
    </AuthLayout>
  );
}
