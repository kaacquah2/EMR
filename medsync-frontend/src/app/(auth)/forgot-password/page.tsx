"use client";

import React, { useState } from "react";
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
        // Backend already returns a generic message; show a single generic error here
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
            If an account exists for {email}, you&apos;ll receive a password reset link.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-flex items-center text-sm font-medium text-[#0B8A96] hover:underline"
          >
            Back to sign in
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
          />
          {error && <p className="text-sm text-[#DC2626]">{error}</p>}
          <Button type="submit" fullWidth disabled={loading}>
            {loading ? "Sending..." : "Send reset link"}
          </Button>
          <Link
            href="/login"
            className="block text-center text-sm text-[#64748B] hover:text-[#0F172A]"
          >
            Back to sign in
          </Link>
        </form>
      )}
    </AuthLayout>
  );
}
