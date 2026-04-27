"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";

export default function UnauthorizedPage() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <Card className="w-full max-w-lg border-[var(--amber-600)]/30 bg-[#FFFBEB]/60" accent="amber">
        <CardContent className="pt-6 text-center">
          {/* Icon */}
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--amber-600)]/10">
            <svg className="h-7 w-7 text-[var(--amber-600)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>

          <h1 className="font-sora text-2xl font-bold text-[var(--gray-900)]">Access Denied</h1>

          {/* UX-23: Show user's current role for context */}
          {user && (
            <p className="mt-2 text-sm text-[var(--gray-500)]">
              You are signed in as <strong className="text-[var(--gray-700)] capitalize">{user.role?.replace("_", " ")}</strong>
              {user.full_name ? ` (${user.full_name})` : ""}.
            </p>
          )}

          <p className="mt-2 text-[var(--gray-500)]">
            You do not have permission to view this page. If you believe this is an error, contact your administrator to request access.
          </p>

          <div className="mt-6 flex flex-col items-center gap-2">
            <Link href="/dashboard">
              <Button>← Back to Dashboard</Button>
            </Link>
            {user?.role && (
              <p className="text-xs text-[var(--gray-500)]">
                Your role: <span className="font-medium capitalize">{user.role.replace("_", " ")}</span>
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
