"use client";

import React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { AlertTriangle, ArrowRight } from "lucide-react";

export const GracePeriodBanner: React.FC = () => {
  const { user } = useAuth();

  if (!user?.totp_grace_period_expires) return null;

  const expiresAt = new Date(user.totp_grace_period_expires);
  const now = new Date();

  if (expiresAt <= now) return null;

  const timeString = expiresAt.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="bg-amber-50 border-b border-amber-200 py-2 px-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-amber-800 text-sm font-medium">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span>
            Two-factor setup required: Please set up your authenticator app by{" "}
            <span className="font-bold underline">{timeString}</span> to maintain access.
          </span>
        </div>
        <Link
          href="/setup-totp"
          className="flex items-center gap-1 text-amber-900 bg-amber-200 hover:bg-amber-300 transition-colors px-3 py-1 rounded-md text-xs font-bold whitespace-nowrap"
        >
          Set up now <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
};
