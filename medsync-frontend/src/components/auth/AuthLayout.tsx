"use client";

import React from "react";
import Link from "next/link";

const CROSS_PATTERN = `url("data:image/svg+xml,%3Csvg width='32' height='32' viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M14 8h4v6h6v4h-6v6h-4v-6H8v-4h6V8z' fill='%23ffffff' fill-opacity='0.08'/%3E%3C/svg%3E")`;

export interface AuthLayoutProps {
  children: React.ReactNode;
  /** Right side header title (e.g. "MedSync") */
  title?: string;
  /** Right side header subtitle */
  subtitle?: string;
}

export function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: brand panel — solid, high-contrast background */}
      <div className="relative hidden bg-[#0C1F3D] lg:block">
        <div
          className="absolute inset-0 bg-gradient-to-b from-[#0C1F3D] via-[#0B8A96] to-[#0C1F3D]"
          style={{ backgroundImage: `${CROSS_PATTERN}` }}
        />
        <div className="relative flex h-full flex-col justify-between p-12 xl:p-16 text-white">
          <div>
            <Link
              href="/login"
              className="font-sora text-xl font-semibold tracking-tight"
              style={{ textShadow: "0 1px 2px rgba(0,0,0,0.35)" }}
            >
              MedSync
            </Link>
          </div>
          <div className="space-y-8">
            <div className="login-float">
              <h2
                className="font-sora text-3xl font-bold leading-tight xl:text-4xl"
                style={{ textShadow: "0 2px 4px rgba(0,0,0,0.45)" }}
              >
                One record.
                <br />
                Every hospital.
              </h2>
              <p
                className="mt-4 max-w-sm text-sm leading-relaxed"
                style={{ textShadow: "0 1px 3px rgba(0,0,0,0.4)" }}
              >
                Ghana Inter-Hospital Electronic Medical Records. Secure, interoperable care across facilities.
              </p>
            </div>
            <div
              className="flex flex-wrap gap-6 text-xs font-medium uppercase tracking-wider"
              style={{ textShadow: "0 1px 3px rgba(0,0,0,0.4)" }}
            >
              <span>Secure</span>
              <span>•</span>
              <span>Interoperable</span>
              <span>•</span>
              <span>Audited</span>
            </div>
            <div className="login-panel-shine relative mt-12 h-16 w-full max-w-xs opacity-95">
              <svg viewBox="0 0 240 48" fill="none" className="h-full w-full" aria-hidden>
                <path
                  d="M0 24 L40 24 L50 12 L60 36 L70 24 L120 24 L130 8 L140 40 L150 24 L200 24 L210 20 L220 28 L240 24"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-white"
                />
                <path
                  d="M0 24 L40 24 L50 12 L60 36 L70 24 L120 24 L130 8 L140 40 L150 24 L200 24 L210 20 L220 28 L240 24"
                  stroke="url(#auth-heartbeat-glow)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.8"
                />
                <defs>
                  <linearGradient id="auth-heartbeat-glow" x1="0" y1="0" x2="240" y2="0">
                    <stop stopColor="#22c1c3" stopOpacity="1" />
                    <stop offset="0.5" stopColor="#ffffff" stopOpacity="1" />
                    <stop offset="1" stopColor="#0e7490" stopOpacity="1" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>
          <div className="login-float-delay flex gap-4">
            <div className="h-10 w-10 rounded-lg bg-white/30 backdrop-blur-sm" aria-hidden />
            <div className="h-10 w-10 rounded-lg bg-white/30 backdrop-blur-sm" aria-hidden />
            <div className="h-10 w-10 rounded-lg bg-amber-300/50 backdrop-blur-sm" aria-hidden />
            <div className="h-10 w-10 rounded-lg bg-emerald-300/50 backdrop-blur-sm" aria-hidden />
          </div>
        </div>
      </div>

      {/* Right: form — soft blue-to-white gradient, not plain white */}
      <div
        className="relative flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-[#E0F2FE] via-[#F0F9FF] to-white px-4 py-10 pt-16 lg:pt-10 lg:px-8"
      >
        <div className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between border-b border-[#0B8A96]/15 bg-white/90 px-4 py-3 backdrop-blur-sm lg:hidden">
          <Link href="/login" className="font-sora text-sm font-semibold text-[#0C1F3D]">
            MedSync
          </Link>
          <span className="text-xs text-[#475569]">One record. Every hospital.</span>
        </div>

        <div className="w-full max-w-[420px] login-form-enter rounded-2xl border border-[#BAE6FD] bg-white p-8 shadow-xl ring-1 ring-[#0B8A96]/10">
          {(title != null || subtitle != null) && (
            <div className="mb-8 text-center lg:text-left">
              {title && (
                <h1 className="font-sora text-2xl font-bold text-[#0C1F3D]">
                  {title}
                </h1>
              )}
              {subtitle && (
                <p className="mt-1 text-sm text-[#475569]">
                  {subtitle}
                </p>
              )}
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}
